from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "supabase_table": settings.supabase_table,
        "match_function": settings.supabase_match_fn,
        "model": settings.openai_model,
    }