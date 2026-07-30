from fastapi import APIRouter, Depends

from app.api.deps import get_powabase_client
from app.clients.powabase_client import PowabaseClient
from app.core.config import settings

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
async def list_documents(
    powabase: PowabaseClient = Depends(get_powabase_client),
):
    listing = await powabase.list_kb_sources(settings.powabase_kb_id)
    return listing["items"]
