import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import (
    get_bearer_token,
    get_current_user,
    get_postgrest_client,
    get_powabase_client,
)
from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import AgentNotFoundError, PowabaseClient
from app.core.config import settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ChatSessionCreate,
    ChatSessionRename,
    SessionDocumentResponse,
)
from app.services.chat_service import ChatRunFailedError, ChatService
from app.services.chatbot_management import ChatbotNotFoundError, get_owned_chatbot
from app.services.chatbot_provisioning import recreate_agent_for_chatbot
from app.services.document_ingestion import (
    SessionNotFoundError,
    ingest_document_for_session,
)
from app.services.ingest_service import ExtractionNotUsableError, PollTimeoutError
from app.services.specialist_management import Specialist
from app.services.specialist_routing import choose_specialist

router = APIRouter(prefix="/chat", tags=["chat"])


async def _load_specialists(
    chatbot_id: str, access_token: str, postgrest: PostgrestClient
) -> list[Specialist]:
    rows = await postgrest.select(
        "chatbot_specialists",
        "id,name,specialty,powabase_agent_id",
        filters={"chatbot_id": chatbot_id},
        access_token=access_token,
    )
    return [
        Specialist(
            id=row["id"],
            name=row["name"],
            specialty=row["specialty"],
            agent_id=row["powabase_agent_id"],
        )
        for row in rows
    ]


async def _specialist_kb_ids(
    specialists: list[Specialist], access_token: str, postgrest: PostgrestClient
) -> dict:
    """Each specialist's own private document knowledge bases (not the
    chatbot's shared ones -- those are identical across every specialist, so
    they carry no signal for telling specialists apart during routing)."""
    result = {}
    for specialist in specialists:
        rows = await postgrest.select(
            "specialist_documents",
            "documents(powabase_knowledge_base_id)",
            filters={"specialist_id": specialist.id},
            access_token=access_token,
        )
        kb_ids = [
            row["documents"]["powabase_knowledge_base_id"]
            for row in rows
            if row.get("documents") and row["documents"].get("powabase_knowledge_base_id")
        ]
        if kb_ids:
            result[specialist.id] = kb_ids
    return result


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
    powabase: PowabaseClient = Depends(get_powabase_client),
):
    try:
        chatbot = await get_owned_chatbot(req.chatbot_id, access_token, postgrest)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    session = None
    if req.session_id:
        session = await postgrest.select_one(
            "chat_sessions",
            {"id": req.session_id},
            "id,powabase_session_id,powabase_agent_id",
            access_token=access_token,
        )
    if session is None:
        session = await postgrest.insert(
            "chat_sessions", {"chatbot_id": chatbot.id}, access_token=access_token
        )

    await postgrest.insert(
        "messages",
        {"session_id": session["id"], "role": "user", "content": req.message},
        access_token=access_token,
    )

    # A session with its own private documents gets its own dedicated
    # Powabase agent (see ingest_document_for_session) and always answers
    # through it, skipping specialist routing entirely, so those documents
    # never leak into a specialist or the chatbot's shared knowledge.
    session_agent_id = session.get("powabase_agent_id")

    chosen_specialist = None
    if not session_agent_id:
        # Like GPT Trainer's multi-agent orchestration: if this chatbot has
        # specialist sub-agents, a lightweight routing step picks the best one
        # for this message; otherwise the parent chatbot's own agent answers.
        # When a specialist has its own private documents, the router can
        # search them (request-scoped, not permanently linked) to make an
        # evidence-based pick instead of matching on specialty text alone.
        specialists = await _load_specialists(chatbot.id, access_token, postgrest)
        specialist_kb_ids = (
            await _specialist_kb_ids(specialists, access_token, postgrest)
            if len(specialists) > 1
            else {}
        )
        chosen_specialist = await choose_specialist(
            req.message,
            specialists,
            chatbot.agent_id,
            powabase,
            specialist_kb_ids=specialist_kb_ids,
        )

    answering_agent_id = (
        session_agent_id
        or (chosen_specialist.agent_id if chosen_specialist else chatbot.agent_id)
    )

    chat_service = ChatService(client=powabase, agent_id=answering_agent_id)
    try:
        try:
            result = await chat_service.get_answer(
                query=req.message,
                # A stored powabase_session_id belongs to whichever agent
                # last answered in this conversation. Only reuse it when the
                # same agent is answering again -- the parent chatbot, or a
                # session with its own dedicated agent; a specialist (a
                # different Powabase agent) always starts its own session,
                # since our own `messages` table -- not Powabase's session --
                # is the durable record of this conversation either way.
                session_id=(
                    session.get("powabase_session_id")
                    if (session_agent_id or not chosen_specialist)
                    else None
                ),
                temperature=req.temperature,
            )
        except AgentNotFoundError:
            # The stored agent was deleted on the Powabase side (e.g. from Studio) --
            # provision a replacement, re-link its knowledge bases, and retry once.
            chatbot = await recreate_agent_for_chatbot(
                chatbot, user["id"], access_token, postgrest, powabase
            )
            chat_service = ChatService(client=powabase, agent_id=chatbot.agent_id)
            result = await chat_service.get_answer(
                query=req.message,
                session_id=None,
                temperature=req.temperature,
            )
    except ChatRunFailedError as e:
        raise HTTPException(status_code=502, detail=f"Powabase run failed: {e.message}")

    if result.powabase_session_id and result.powabase_session_id != session.get(
        "powabase_session_id"
    ):
        await postgrest.update(
            "chat_sessions",
            {"id": session["id"]},
            {"powabase_session_id": result.powabase_session_id},
            access_token=access_token,
        )

    await postgrest.insert(
        "messages",
        {"session_id": session["id"], "role": "assistant", "content": result.answer},
        access_token=access_token,
    )

    return ChatResponse(
        answer=result.answer,
        sources=result.sources,
        session_id=session["id"],
        specialist_name=chosen_specialist.name if chosen_specialist else None,
    )


@router.post("/sessions")
async def create_session(
    req: ChatSessionCreate,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    try:
        chatbot = await get_owned_chatbot(req.chatbot_id, access_token, postgrest)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chatbot not found")

    return await postgrest.insert(
        "chat_sessions", {"chatbot_id": chatbot.id}, access_token=access_token
    )


@router.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    req: ChatSessionRename,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    rows = await postgrest.update(
        "chat_sessions", {"id": session_id}, {"title": req.title}, access_token=access_token
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return rows[0]


@router.get("/sessions")
async def list_sessions(
    chatbot_id: str,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    return await postgrest.select(
        "chat_sessions",
        "id,title,created_at",
        filters={"chatbot_id": chatbot_id},
        order="created_at.desc",
        access_token=access_token,
    )


@router.get("/inbox")
async def list_inbox(
    chatbot_id: str | None = None,
    unread_only: bool = False,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    """Every visitor conversation across the caller's chatbots (public share
    link only -- not the owner's own test chats), most recently active
    first. RLS on chat_sessions already scopes this to chatbots the caller
    owns, so no explicit ownership filter is needed here."""
    filters = {"origin": "public"}
    if chatbot_id:
        filters["chatbot_id"] = chatbot_id
    if unread_only:
        filters["unread"] = "true"

    return await postgrest.select(
        "chat_sessions",
        "id,chatbot_id,title,created_at,last_message_at,last_message_preview,"
        "unread,chatbots(name)",
        filters=filters,
        order="last_message_at.desc.nullslast",
        access_token=access_token,
    )


@router.post("/sessions/{session_id}/read")
async def mark_session_read(
    session_id: str,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    rows = await postgrest.update(
        "chat_sessions", {"id": session_id}, {"unread": False}, access_token=access_token
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return rows[0]


@router.post("/sessions/{session_id}/documents", response_model=SessionDocumentResponse)
async def upload_session_document(
    session_id: str,
    file: UploadFile = File(...),
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
    powabase: PowabaseClient = Depends(get_powabase_client),
):
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {e}")

    try:
        result = await ingest_document_for_session(
            content=content,
            filename=file.filename,
            mime_type=file.content_type,
            session_id=session_id,
            access_token=access_token,
            service_role_key=settings.powabase_api_key,
            postgrest=postgrest,
            powabase=powabase,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except ExtractionNotUsableError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except PollTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (402, 503):
            raise HTTPException(
                status_code=e.response.status_code, detail=f"Powabase request failed: {e}"
            )
        raise HTTPException(status_code=502, detail=f"Powabase request failed: {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Powabase unreachable: {e}")

    return SessionDocumentResponse(
        document_id=result.document_id,
        is_new=result.is_new,
        index_status=result.index_status,
        session_document_id=result.session_document_id,
    )


@router.get("/sessions/{session_id}/documents")
async def list_session_documents(
    session_id: str,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    return await postgrest.select(
        "chat_session_documents",
        "id,display_name,created_at,documents(index_status,original_filename)",
        filters={"session_id": session_id},
        order="created_at.asc",
        access_token=access_token,
    )


@router.get("/sessions/{session_id}/messages")
async def list_session_messages(
    session_id: str,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    return await postgrest.select(
        "messages",
        "id,role,content,created_at",
        filters={"session_id": session_id},
        order="created_at.asc",
        access_token=access_token,
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    access_token: str = Depends(get_bearer_token),
    user: dict = Depends(get_current_user),
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    rows = await postgrest.delete(
        "chat_sessions", {"id": session_id}, access_token=access_token
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Conversation not found")
