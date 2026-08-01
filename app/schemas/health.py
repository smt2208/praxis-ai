"""
app/schemas/health.py

Health check response model.
"""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    qdrant: str
