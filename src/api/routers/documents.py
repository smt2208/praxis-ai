import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from llama_cloud import APIConnectionError, APIStatusError
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from src.core.security import get_current_user
from src.core.config import settings
from src.db.session import get_db
from src.db.models import User
from src.agent.document import process_and_index_document
from src.services.chat_service import ensure_conversation_access
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/upload/{conversation_id}")
async def upload_document(
    conversation_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(file.filename or "upload").name
    file_path = upload_dir / f"{uuid.uuid4()}_{filename}"
    
    try:
        await ensure_conversation_access(db, current_user.id, conversation_id)
        async with aiofiles.open(file_path, "wb") as buffer:
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_size_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File is too large",
                    )
                await buffer.write(chunk)
            
        # Process and index with LlamaParse and Qdrant
        num_docs = await process_and_index_document(str(file_path), str(current_user.id), str(conversation_id))
        
        return {"message": "Document parsed and indexed successfully", "chunks": num_docs}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except APIConnectionError:
        logger.exception("LlamaCloud could not be reached while processing an upload")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document parsing service is temporarily unavailable. Please try again.",
        )
    except APIStatusError as exc:
        logger.exception("LlamaCloud rejected document upload with status %s", exc.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Document parsing service rejected this file. Check the file type and LlamaCloud API key.",
        )
    except Exception:
        logger.exception("Document upload processing failed")
        raise HTTPException(status_code=500, detail="Unable to process the document")
    finally:
        await file.close()
        if file_path.exists():
            file_path.unlink()
