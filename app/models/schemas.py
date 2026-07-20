from typing import Any, Optional

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    source_id: str
    indexed_source_id: str
    status: str


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)


class SourceChunk(BaseModel):
    content_preview: str
    metadata: dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]