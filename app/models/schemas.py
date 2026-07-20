from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    chunks_added: int
    table_name: str
    match_function: str


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(4, ge=1, le=20)
    filter: Optional[Dict[str, Any]] = None
    match_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    model: Optional[str] = None
    max_output_tokens: Optional[int] = Field(None, ge=50, le=4000)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)


class SourceChunk(BaseModel):
    content_preview: str
    metadata: Dict[str, Any]


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]