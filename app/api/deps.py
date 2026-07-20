from fastapi import Depends

from app.clients.powabase_client import PowabaseClient
from app.core.config import settings
from app.services.chat_service import ChatService
from app.services.ingest_service import IngestService


def get_powabase_client() -> PowabaseClient:
    return PowabaseClient(settings.powabase_base_url, settings.powabase_api_key)


def get_ingest_service(
    client: PowabaseClient = Depends(get_powabase_client),
) -> IngestService:
    return IngestService(client=client, kb_id=settings.powabase_kb_id)


def get_chat_service(
    client: PowabaseClient = Depends(get_powabase_client),
) -> ChatService:
    return ChatService(client=client, agent_id=settings.powabase_agent_id)
