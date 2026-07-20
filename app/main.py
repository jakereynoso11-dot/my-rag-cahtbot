from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.chat import router as chat_router


def create_app() -> FastAPI:
    app = FastAPI(title="RAG Chatbot API", version="1.0.0")

    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(chat_router)

    return app


app = create_app()