"""
app/db/migrations/__init__.py

Database migrations package.
Executes idempotent schema DDL statements and incremental column migrations.
"""
import asyncpg
from app.db.migrations.schema import MIGRATION_STATEMENTS


async def run_migrations(conn: asyncpg.Connection) -> None:
    """
    Execute all schema creation, column addition, and index creation migrations sequentially.
    All statements are idempotent.
    """
    for statement in MIGRATION_STATEMENTS:
        await conn.execute(statement)


__all__ = ["run_migrations"]
