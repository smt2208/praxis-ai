"""
app/schemas/ingest.py

Document ingestion request and response models.
"""
from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Trigger document ingestion from an S3 URL or local path."""
    source_url: str = Field(..., description="S3 URL or public URL of the document to ingest")
    conversation_id: str = Field(..., description="The conversation ID to scope this document to")


class IngestResponse(BaseModel):
    message: str
    documents_stored: int
