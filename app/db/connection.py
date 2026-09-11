"""
app/db/connection.py

Database connection pool lifecycle and DDL migrations.
Called once at application startup via the FastAPI lifespan.
"""
import asyncpg
from app.config import Settings
from app.db.migrations import run_migrations


async def init_db_pool(settings: Settings) -> asyncpg.Pool:
    """
    Create the asyncpg connection pool and run idempotent DDL migrations.

    Delegates table definitions, column additions, and index creation on startup
    to app.db.migrations. All statements use 'IF NOT EXISTS' to ensure safe,
    repeatable initialization across app reboots and multi-worker deployments.
    """
    pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        min_size=2,
        max_size=10,
    )
    async with pool.acquire() as conn:
        await run_migrations(conn)
    return pool

