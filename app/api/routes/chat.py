from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_bearer_token,
    get_current_user,
    get_postgrest_client,
    get_powabase_client,
)
from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import AgentNotFoundError, PowabaseClient
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatRunFailedError, ChatService
from app.services.chatbot_management import ChatbotNotFoundError, get_owned_chatbot
from app.services.chatbot_provisioning import recreate_agent_for_chatbot

router = APIRouter(prefix="/chat", tags=["chat"])


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
            "id,powabase_session_id",
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

    chat_service = ChatService(client=powabase, agent_id=chatbot.agent_id)
    try:
        try:
            result = await chat_service.get_answer(
                query=req.message,
                session_id=session.get("powabase_session_id"),
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

    return ChatResponse(answer=result.answer, sources=result.sources, session_id=session["id"])


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
