import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_ingest_service
from app.models.schemas import IngestResponse
from app.services.ingest_service import (
    ExtractionNotUsableError,
    IngestService,
    PollTimeoutError,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    ingest_service: IngestService = Depends(get_ingest_service),
):
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {e}")

    try:
        result = await ingest_service.ingest_pdf(file.filename, content)
    except ExtractionNotUsableError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except PollTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (402, 503):
            raise HTTPException(status_code=e.response.status_code, detail=f"Powabase request failed: {e}")
        else:
            raise HTTPException(status_code=502, detail=f"Powabase request failed: {e}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Powabase unreachable: {e}")

    return IngestResponse(
        source_id=result.source_id,
        indexed_source_id=result.indexed_source_id,
        status=result.status,
    )