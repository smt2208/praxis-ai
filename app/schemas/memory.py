"""
app/schemas/memory.py

Pydantic schemas for memory management.
"""
from pydantic import BaseModel


class MemoryToggleRequest(BaseModel):
    enabled: bool
