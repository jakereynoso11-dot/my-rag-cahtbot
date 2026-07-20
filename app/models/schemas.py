from typing import Optional

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    source_id: str
    indexed_source_id: str
    status: str


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)