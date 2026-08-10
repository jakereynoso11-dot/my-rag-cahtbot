from typing import Optional

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    document_id: str
    is_new: bool
    index_status: str
    chatbot_document_id: str


class ChatbotCreate(BaseModel):
    name: str = Field(..., min_length=1)
    purpose: Optional[str] = None
    system_prompt: Optional[str] = None


class ChatbotRename(BaseModel):
    name: str = Field(..., min_length=1)


class ChatbotResponse(BaseModel):
    id: str
    name: str
    purpose: Optional[str] = None
    created_at: str


class ChatRequest(BaseModel):
    chatbot_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)


class ChatResponse(BaseModel):
    answer: str
    sources: list = []
    session_id: str
    specialist_name: Optional[str] = None


class SpecialistCreate(BaseModel):
    name: str = Field(..., min_length=1)
    specialty: str = Field(..., min_length=1)
    system_prompt: Optional[str] = None


class SpecialistResponse(BaseModel):
    id: str
    name: str
    specialty: str
    created_at: str
