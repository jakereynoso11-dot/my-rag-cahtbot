import hashlib
from dataclasses import dataclass
from typing import Optional

from app.clients.postgrest_client import PostgrestClient
from app.clients.powabase_client import PowabaseClient
from app.services.ingest_service import ExtractionNotUsableError, IngestService

__all__ = [
    "DocumentIngestResult",
    "compute_sha256",
    "get_chatbot_agent_id",
    "ingest_document_for_chatbot",
]


@dataclass
class DocumentIngestResult:
    document_id: str
    is_new: bool
    index_status: str
    chatbot_document_id: str


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def get_chatbot_agent_id(
    chatbot_id: str, access_token: str, postgrest: PostgrestClient
) -> Optional[str]:
    """Look up a chatbot's Powabase agent id, scoped to what `access_token`'s
    user can see (RLS on public.chatbots limits this to owned chatbots)."""
    row = await postgrest.select_one(
        "chatbots",
        {"id": chatbot_id},
        "id,powabase_agent_id",
        access_token=access_token,
    )
    return row["powabase_agent_id"] if row else None


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

    return DocumentIngestResult(
        document_id=document_id,
        is_new=doc["is_new"],
        index_status=index_status,
        chatbot_document_id=chatbot_document["id"],
    )
