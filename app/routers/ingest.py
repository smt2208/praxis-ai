import os
import shutil
import tempfile
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from app.auth.dependencies import get_current_user
from app.dependencies import get_pool
from app.database import mark_conversation_has_documents
from app.schemas import IngestRequest, IngestResponse
from scripts.ingestion import ingest_document

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])


@router.post("", response_model=IngestResponse)
async def ingest(
    body: IngestRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Ingest a document from a URL into the authenticated user's private knowledge base.
    """
    try:
        count = await ingest_document(
            source_url=body.source_url,
            user_id=current_user["id"],
            conversation_id=body.conversation_id,
        )
        await mark_conversation_has_documents(pool, body.conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")

    return IngestResponse(
        message="Document ingested successfully.",
        documents_stored=count,
    )


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Ingest a document directly via file upload (multipart/form-data).
    """
    _, ext = os.path.splitext(file.filename or "")
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        count = await ingest_document(
            source_url=tmp_path,
            user_id=current_user["id"],
            conversation_id=conversation_id,
        )
        await mark_conversation_has_documents(pool, conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return IngestResponse(
        message="File ingested successfully.",
        documents_stored=count,
    )
