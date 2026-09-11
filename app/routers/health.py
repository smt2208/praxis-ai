"""
app/routers/health.py

System health and readiness probes for load balancers and orchestrators.
"""
import asyncio
import asyncpg
from fastapi import APIRouter, Depends, Response, status
from qdrant_client import QdrantClient

from app.config import get_settings
from app.schemas import HealthResponse
from app.core.dependencies import get_pool

settings = get_settings()
router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse)
async def health_check(response: Response, pool: asyncpg.Pool = Depends(get_pool)):
    """
    Health check probe inspecting PostgreSQL and Qdrant cluster connectivity.
    Returns 'healthy' when all underlying data stores are reachable, or 'degraded' if any fail.
    """
    # Check DB
    try:
        await pool.fetchval("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    # Check Qdrant
    try:
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        await asyncio.to_thread(client.get_collections)
        qdrant_status = "ok"
    except Exception as e:
        qdrant_status = f"error: {e}"

    overall = "healthy" if db_status == "ok" and qdrant_status == "ok" else "degraded"
    if overall != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status=overall, database=db_status, qdrant=qdrant_status)
