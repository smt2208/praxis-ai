"""
app/db/migrations/schema.py

Schema DDL statements and incremental column migrations.
All statements are idempotent using 'IF NOT EXISTS'.
"""

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
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
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

_ADD_MESSAGES_METADATA_COL = """
ALTER TABLE messages ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
"""

# ── Performance Indexes ──────────────────────────────────────────────────
# 1. idx_conversations_user_id: Accelerates user conversation listing and ownership checks.
# 2. idx_messages_conversation_id_created: Composite index to optimize history fetching
#    ordered by timestamp without requiring slow in-memory file sorts.
# 3. idx_conv_docs_conversation_id: Fast lookup for conversation document presence & deduplication.
# 4. idx_refresh_tokens_user_id: Quick revocation of all user tokens on logout.
# 5. idx_messages_metadata: GIN index for JSONB metadata lookups.
_CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations (user_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id_created ON messages (conversation_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_conv_docs_conversation_id ON conversation_documents (conversation_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_messages_metadata ON messages USING gin (metadata);
"""

MIGRATION_STATEMENTS = [
    _CREATE_TABLES_SQL,
    _ADD_CONVERSATION_HAS_DOCUMENTS_COL,
    _ADD_EMAIL_VERIFICATION_COLS,
    _ADD_PASSWORD_RESET_COLS,
    _ADD_FULL_NAME_COL,
    _ADD_MEMORY_ENABLED_COL,
    _ADD_EXTENDED_PROFILE_COLS,
    _ADD_MESSAGES_METADATA_COL,
    _CREATE_INDEXES_SQL,
]
