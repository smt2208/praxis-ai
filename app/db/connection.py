"""
app/db/connection.py

Database connection pool lifecycle and DDL migrations.
Called once at application startup via the FastAPI lifespan.
"""
import asyncpg
from app.config import Settings


_CREATE_TABLES_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(255) DEFAULT 'New Conversation',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(50) CHECK (role IN ('user', 'assistant', 'system')) NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    token      TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_ADD_CONVERSATION_HAS_DOCUMENTS_COL = """
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS has_documents BOOLEAN NOT NULL DEFAULT FALSE;
"""

_ADD_EMAIL_VERIFICATION_COLS = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified       BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token TEXT;

-- Auto-verify legacy users created before email verification was added
UPDATE users SET is_verified = TRUE WHERE verification_token IS NULL AND is_verified = FALSE;
"""


_ADD_PASSWORD_RESET_COLS = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token       TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expires_at  TIMESTAMP;
"""

_ADD_FULL_NAME_COL = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(100);
"""

_ADD_MEMORY_ENABLED_COL = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS memory_enabled BOOLEAN NOT NULL DEFAULT TRUE;
"""

_ADD_EXTENDED_PROFILE_COLS = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS age        INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS profession VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS city       VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS state      VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS country    VARCHAR(100);
"""


async def init_db_pool(settings: Settings) -> asyncpg.Pool:
    """Create the asyncpg connection pool and ensure all tables exist."""
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
        await conn.execute(_CREATE_TABLES_SQL)
        await conn.execute(_ADD_CONVERSATION_HAS_DOCUMENTS_COL)
        await conn.execute(_ADD_EMAIL_VERIFICATION_COLS)
        await conn.execute(_ADD_PASSWORD_RESET_COLS)
        await conn.execute(_ADD_FULL_NAME_COL)
        await conn.execute(_ADD_MEMORY_ENABLED_COL)
        await conn.execute(_ADD_EXTENDED_PROFILE_COLS)
    return pool

