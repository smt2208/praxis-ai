import asyncpg
from fastapi import Request

async def get_pool(request: Request) -> asyncpg.Pool:
    """Inject the asyncpg pool from app.state into any endpoint."""
    return request.app.state.db_pool
