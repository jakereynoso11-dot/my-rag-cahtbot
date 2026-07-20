import os
from fastapi import APIRouter, File, UploadFile, HTTPException

from app.core.config import settings
from app.models.schemas import IngestResponse
from app.clients.supabase_client import get_supabase_client
from app.clients.embeddings import get_embeddings
from app.services.ingest_service import IngestService

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    chunk_size: int = settings.chunk_size,
    chunk_overlap: int = settings.chunk_overlap,
    keep_file: bool = False,
):
    supabase = get_supabase_client()
    embeddings = get_embeddings()
    ingest_service = IngestService(supabase=supabase, embeddings=embeddings)

    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {e}")

    tmp_path = ingest_service.save_upload_to_tmp(file.filename, content)

    try:
        chunks_added = ingest_service.ingest_pdf_path(
            tmp_path, chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        return IngestResponse(
            chunks_added=chunks_added,
            table_name=settings.supabase_table,
            match_function=settings.supabase_match_fn,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")
    finally:
        if not keep_file:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass