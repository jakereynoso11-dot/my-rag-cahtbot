from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_postgrest_client, get_powabase_client
from app.api.routes.chat import _load_specialists, _specialist_kb_ids
from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import AgentNotFoundError, PowabaseClient
from app.core.config import settings
from app.models.schemas import ChatResponse, PublicChatbotResponse, PublicChatRequest
from app.services.chat_service import ChatRunFailedError, ChatService
from app.services.chatbot_management import (
    ChatbotNotFoundError,
    get_chatbot_by_share_token,
)
from app.services.chatbot_provisioning import recreate_agent_for_chatbot
from app.services.specialist_routing import choose_specialist

router = APIRouter(prefix="/public/chatbots", tags=["public-chat"])


@router.get("/{share_token}", response_model=PublicChatbotResponse)
async def get_public_chatbot(
    share_token: str,
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    row = await postgrest.select_one(
        "chatbots",
        {"share_token": share_token},
        "name,purpose",
        access_token=settings.powabase_api_key,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Chat link not found")
    return PublicChatbotResponse(name=row["name"], purpose=row.get("purpose"))


@router.post("/{share_token}/chat", response_model=ChatResponse)
async def public_chat(
    share_token: str,
    req: PublicChatRequest,
    postgrest: PostgrestClient = Depends(get_postgrest_client),
    powabase: PowabaseClient = Depends(get_powabase_client),
):
    # There's no visitor JWT for an anonymous public chat -- every postgrest
    # call here uses the Powabase service role key instead, and every lookup
    # is scoped explicitly in application code (chatbot_id checks below)
    # rather than relying on RLS the way the authenticated /chat route does.
    service_role_key = settings.powabase_api_key

    try:
        chatbot = await get_chatbot_by_share_token(share_token, service_role_key, postgrest)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chat link not found")

    session = None
    if req.session_id:
        candidate = await postgrest.select_one(
            "chat_sessions",
            {"id": req.session_id},
            "id,chatbot_id,powabase_session_id,powabase_agent_id",
            access_token=service_role_key,
        )
        # Only reuse it if it actually belongs to this chatbot -- otherwise a
        # visitor passing an unrelated/stale session id just gets a fresh one
        # instead of erroring.
        if candidate and candidate["chatbot_id"] == chatbot.id:
            session = candidate
    if session is None:
        session = await postgrest.insert(
            "chat_sessions", {"chatbot_id": chatbot.id}, access_token=service_role_key
        )

    await postgrest.insert(
        "messages",
        {"session_id": session["id"], "role": "user", "content": req.message},
        access_token=service_role_key,
    )

    session_agent_id = session.get("powabase_agent_id")

    chosen_specialist = None
    if not session_agent_id:
        specialists = await _load_specialists(chatbot.id, service_role_key, postgrest)
        specialist_kb_ids = (
            await _specialist_kb_ids(specialists, service_role_key, postgrest)
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
                session_id=(
                    session.get("powabase_session_id")
                    if (session_agent_id or not chosen_specialist)
                    else None
                ),
            )
        except AgentNotFoundError:
            chatbot = await recreate_agent_for_chatbot(
                chatbot, "public-link", service_role_key, postgrest, powabase
            )
            chat_service = ChatService(client=powabase, agent_id=chatbot.agent_id)
            result = await chat_service.get_answer(query=req.message, session_id=None)
    except ChatRunFailedError as e:
        raise HTTPException(status_code=502, detail=f"Powabase run failed: {e.message}")

    if result.powabase_session_id and result.powabase_session_id != session.get(
        "powabase_session_id"
    ):
        await postgrest.update(
            "chat_sessions",
            {"id": session["id"]},
            {"powabase_session_id": result.powabase_session_id},
            access_token=service_role_key,
        )

    await postgrest.insert(
        "messages",
        {"session_id": session["id"], "role": "assistant", "content": result.answer},
        access_token=service_role_key,
    )

    return ChatResponse(
        answer=result.answer,
        sources=result.sources,
        session_id=session["id"],
        specialist_name=chosen_specialist.name if chosen_specialist else None,
    )


@router.get("/{share_token}/chat/sessions/{session_id}/messages")
async def list_public_session_messages(
    share_token: str,
    session_id: str,
    postgrest: PostgrestClient = Depends(get_postgrest_client),
):
    service_role_key = settings.powabase_api_key

    try:
        chatbot = await get_chatbot_by_share_token(share_token, service_role_key, postgrest)
    except ChatbotNotFoundError:
        raise HTTPException(status_code=404, detail="Chat link not found")

    session = await postgrest.select_one(
        "chat_sessions",
        {"id": session_id},
        "id,chatbot_id",
        access_token=service_role_key,
    )
    if not session or session["chatbot_id"] != chatbot.id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return await postgrest.select(
        "messages",
        "id,role,content,created_at",
        filters={"session_id": session_id},
        order="created_at.asc",
        access_token=service_role_key,
    )
