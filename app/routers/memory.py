"""
app/routers/memory.py

Endpoints for managing long-term memory settings and clearing user memory.
"""
import asyncio
import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.dependencies import get_pool
from app.db import set_memory_enabled, get_memory_enabled
from app.services.memory import delete_all_memories

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/memory", tags=["Memory"])


class MemoryToggleRequest(BaseModel):
    enabled: bool


@router.patch("/toggle", status_code=status.HTTP_200_OK)
async def toggle_memory(
    body: MemoryToggleRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """Enable or disable long-term memory for the current user."""
    await set_memory_enabled(pool, current_user["id"], body.enabled)
    return {"memory_enabled": body.enabled, "detail": f"Long-term memory {'enabled' if body.enabled else 'disabled'}."}


@router.delete("", status_code=status.HTTP_200_OK)
async def clear_memory(
    current_user: dict = Depends(get_current_user),
):
    """Delete all stored long-term memories for the current user."""
    await asyncio.to_thread(delete_all_memories, current_user["id"])
    return {"detail": "All long-term memories have been cleared."}
