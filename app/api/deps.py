from typing import Optional

from fastapi import Depends, Header, HTTPException

from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient
from app.core.config import settings
from app.services.chat_service import ChatService
from app.services.ingest_service import IngestService


def get_powabase_client() -> PowabaseClient:
    return PowabaseClient(settings.powabase_base_url, settings.powabase_api_key)


def get_postgrest_client() -> PostgrestClient:
    return PostgrestClient(settings.powabase_base_url, settings.powabase_api_key)


def get_bearer_token(authorization: Optional[str] = Header(None)) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401, detail="Missing or malformed Authorization header"
        )
    return token


def get_ingest_service(
    client: PowabaseClient = Depends(get_powabase_client),
) -> IngestService:
    return IngestService(client=client, kb_id=settings.powabase_kb_id)


def get_chat_service(
    client: PowabaseClient = Depends(get_powabase_client),
) -> ChatService:
    return ChatService(client=client, agent_id=settings.powabase_agent_id)
