import shutil
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from src.core.security import get_current_user
from src.db.models import User
from src.agent.document import process_and_index_document
import os
import uuid

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/upload/{conversation_id}")
async def upload_document(
    conversation_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # Ensure temporary upload directory exists
    upload_dir = "data/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
    
    try:
        async with aiofiles.open(file_path, "wb") as buffer:
            content = await file.read()
            await buffer.write(content)
            
        # Process and index with LlamaParse and Qdrant
        num_docs = await process_and_index_document(file_path, str(current_user.id), str(conversation_id))
        
        return {"message": "Document parsed and indexed successfully", "chunks": num_docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
