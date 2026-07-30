from typing import Optional

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    document_id: str
    is_new: bool
    index_status: str
    chatbot_document_id: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)


class ChatResponse(BaseModel):
    answer: str
    sources: list = []
    session_id: str
