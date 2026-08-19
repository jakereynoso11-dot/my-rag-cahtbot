import hashlib
from dataclasses import dataclass
from typing import Optional

from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient
from app.services.chatbot_provisioning import SYSTEM_PROMPT
from app.services.ingest_service import ExtractionNotUsableError, IngestService

__all__ = [
    "DocumentIngestResult",
    "SessionDocumentIngestResult",
    "SpecialistDocumentIngestResult",
    "SessionNotFoundError",
    "SpecialistNotFoundError",
    "compute_sha256",
    "ingest_document_for_chatbot",
    "ingest_document_for_session",
    "ingest_document_for_specialist",
]


class SessionNotFoundError(Exception):
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Chat session {session_id} not found")


class SpecialistNotFoundError(Exception):
    def __init__(self, specialist_id: str):
        self.specialist_id = specialist_id
        super().__init__(f"Specialist {specialist_id} not found")


@dataclass
class DocumentIngestResult:
    document_id: str
    is_new: bool
    index_status: str
    chatbot_document_id: str


@dataclass
class SessionDocumentIngestResult:
    document_id: str
    is_new: bool
    index_status: str
    session_document_id: str


@dataclass
class SpecialistDocumentIngestResult:
    document_id: str
    is_new: bool
    index_status: str
    specialist_document_id: str


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def _specialist_agent_ids(
    chatbot_id: str, access_token: str, postgrest: PostgrestClient
) -> list:
    rows = await postgrest.select(
        "chatbot_specialists",
        "powabase_agent_id",
        filters={"chatbot_id": chatbot_id},
        access_token=access_token,
    )
    return [row["powabase_agent_id"] for row in rows]


async def _ensure_document_indexed(
    *,
    content: bytes,
    filename: str,
    mime_type: Optional[str],
    access_token: str,
    service_role_key: str,
    postgrest: PostgrestClient,
    powabase: PowabaseClient,
) -> tuple[str, str, str, bool]:
    """Registers the document (deduped by content hash) and makes sure it has
    an indexed, dedicated Powabase knowledge base. Returns
    (document_id, kb_id, index_status, is_new)."""
    content_sha256 = compute_sha256(content)

    rows = await postgrest.rpc(
        "register_or_get_document",
        {
            "p_content_sha256": content_sha256,
            "p_byte_size": len(content),
            "p_mime_type": mime_type,
            "p_original_filename": filename,
        },
        access_token=access_token,
    )
    doc = rows[0]
    document_id = doc["id"]
    kb_id = doc["powabase_knowledge_base_id"]
    index_status = doc["index_status"]

    if not kb_id or index_status != "indexed":
        kb = await powabase.create_knowledge_base(f"doc-{content_sha256[:12]}")
        kb_id = kb["id"]

        try:
            ingest_result = await IngestService(client=powabase, kb_id=kb_id).ingest_pdf(
                filename, content
            )
        except ExtractionNotUsableError as exc:
            await postgrest.update(
                "documents",
                {"id": document_id},
                {
                    "powabase_source_id": exc.source_id,
                    "powabase_knowledge_base_id": kb_id,
                    "index_status": "failed",
                    "index_error": str(exc),
                },
                access_token=service_role_key,
            )
            raise

        index_status = ingest_result.status
        await postgrest.update(
            "documents",
            {"id": document_id},
            {
                "powabase_source_id": ingest_result.source_id,
                "powabase_knowledge_base_id": kb_id,
                "index_status": index_status,
            },
            access_token=service_role_key,
        )

    return document_id, kb_id, index_status, doc["is_new"]


async def ingest_document_for_chatbot(
    *,
    content: bytes,
    filename: str,
    mime_type: Optional[str],
    chatbot_id: str,
    agent_id: str,
    access_token: str,
    service_role_key: str,
    postgrest: PostgrestClient,
    powabase: PowabaseClient,
) -> DocumentIngestResult:
    document_id, kb_id, index_status, is_new = await _ensure_document_indexed(
        content=content,
        filename=filename,
        mime_type=mime_type,
        access_token=access_token,
        service_role_key=service_role_key,
        postgrest=postgrest,
        powabase=powabase,
    )

    chatbot_document = await postgrest.rpc(
        "attach_document_to_chatbot",
        {
            "p_document_id": document_id,
            "p_chatbot_id": chatbot_id,
            "p_display_name": filename,
        },
        access_token=access_token,
    )

    await powabase.add_knowledge_base_to_agent(agent_id, kb_id)

    for specialist_agent_id in await _specialist_agent_ids(
        chatbot_id, access_token, postgrest
    ):
        await powabase.add_knowledge_base_to_agent(specialist_agent_id, kb_id)

    return DocumentIngestResult(
        document_id=document_id,
        is_new=is_new,
        index_status=index_status,
        chatbot_document_id=chatbot_document["id"],
    )


async def ingest_document_for_session(
    *,
    content: bytes,
    filename: str,
    mime_type: Optional[str],
    session_id: str,
    access_token: str,
    service_role_key: str,
    postgrest: PostgrestClient,
    powabase: PowabaseClient,
) -> SessionDocumentIngestResult:
    """Indexes a document for a single chat session only. The session gets
    its own dedicated Powabase agent (created lazily on first upload) so the
    document never becomes visible to the chatbot's other conversations."""
    session = await postgrest.select_one(
        "chat_sessions",
        {"id": session_id},
        "id,powabase_agent_id",
        access_token=access_token,
    )
    if not session:
        raise SessionNotFoundError(session_id)

    document_id, kb_id, index_status, is_new = await _ensure_document_indexed(
        content=content,
        filename=filename,
        mime_type=mime_type,
        access_token=access_token,
        service_role_key=service_role_key,
        postgrest=postgrest,
        powabase=powabase,
    )

    session_document = await postgrest.insert(
        "chat_session_documents",
        {"session_id": session_id, "document_id": document_id, "display_name": filename},
        access_token=access_token,
    )

    session_agent_id = session.get("powabase_agent_id")
    if not session_agent_id:
        agent = await powabase.create_agent(f"session-{session_id}", SYSTEM_PROMPT)
        session_agent_id = agent["id"]
        await postgrest.update(
            "chat_sessions",
            {"id": session_id},
            {"powabase_agent_id": session_agent_id},
            access_token=access_token,
        )

    await powabase.add_knowledge_base_to_agent(session_agent_id, kb_id)

    return SessionDocumentIngestResult(
        document_id=document_id,
        is_new=is_new,
        index_status=index_status,
        session_document_id=session_document["id"],
    )


async def ingest_document_for_specialist(
    *,
    content: bytes,
    filename: str,
    mime_type: Optional[str],
    specialist_id: str,
    access_token: str,
    service_role_key: str,
    postgrest: PostgrestClient,
    powabase: PowabaseClient,
) -> SpecialistDocumentIngestResult:
    """Indexes a document for a single specialist only -- it's linked to that
    specialist's own agent, not the parent chatbot or sibling specialists, so
    it trains just this one specialist on top of whatever the chatbot already
    shares with it."""
    specialist = await postgrest.select_one(
        "chatbot_specialists",
        {"id": specialist_id},
        "id,powabase_agent_id",
        access_token=access_token,
    )
    if not specialist:
        raise SpecialistNotFoundError(specialist_id)

    document_id, kb_id, index_status, is_new = await _ensure_document_indexed(
        content=content,
        filename=filename,
        mime_type=mime_type,
        access_token=access_token,
        service_role_key=service_role_key,
        postgrest=postgrest,
        powabase=powabase,
    )

    specialist_document = await postgrest.insert(
        "specialist_documents",
        {"specialist_id": specialist_id, "document_id": document_id, "display_name": filename},
        access_token=access_token,
    )

    await powabase.add_knowledge_base_to_agent(specialist["powabase_agent_id"], kb_id)

    return SpecialistDocumentIngestResult(
        document_id=document_id,
        is_new=is_new,
        index_status=index_status,
        specialist_document_id=specialist_document["id"],
    )
