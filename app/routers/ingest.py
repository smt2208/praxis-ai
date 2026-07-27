import os
import tempfile
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from app.auth.dependencies import get_current_user
from app.dependencies import get_pool
from app.database import mark_conversation_has_documents, add_conversation_document, verify_conversation_ownership
from app.schemas import IngestRequest, IngestResponse
from scripts.ingestion import ingest_document

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.pptx', '.txt', '.md'}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("", response_model=IngestResponse)
async def ingest(
    body: IngestRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Ingest a document from a URL into the authenticated user's private knowledge base.
    """
    owns = await verify_conversation_ownership(pool, body.conversation_id, current_user["id"])
    if not owns:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    try:
        count = await ingest_document(
            source_url=body.source_url,
            user_id=current_user["id"],
            conversation_id=body.conversation_id,
        )
        filename = body.source_url.split("/")[-1].split("?")[0] or "document"
        await mark_conversation_has_documents(pool, body.conversation_id)
        await add_conversation_document(pool, body.conversation_id, filename)
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
    owns = await verify_conversation_ownership(pool, conversation_id, current_user["id"])
    if not owns:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum upload size is 20 MB.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        count = await ingest_document(
            source_url=tmp_path,
            user_id=current_user["id"],
            conversation_id=conversation_id,
        )
        filename = file.filename or "uploaded_file"
        await mark_conversation_has_documents(pool, conversation_id)
        await add_conversation_document(pool, conversation_id, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return IngestResponse(
        message="File ingested successfully.",
        documents_stored=count,
    )
