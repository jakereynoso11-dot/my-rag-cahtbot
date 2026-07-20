from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "powabase_base_url": settings.powabase_base_url,
        "knowledge_base_id": settings.powabase_kb_id,
        "agent_id": settings.powabase_agent_id,
    }