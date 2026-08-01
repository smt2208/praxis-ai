"""
app/db — Database access layer.

Re-exports all public functions so consumers can use:
    from app.db import get_history, save_message, create_user, ...
"""
from app.db.connection import init_db_pool

from app.db.users import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    set_verification_token,
    verify_email_token,
)

from app.db.conversations import (
    create_conversation,
    get_conversations_by_user,
    delete_conversation,
    verify_conversation_ownership,
    get_conversation_has_documents,
    mark_conversation_has_documents,
    get_conversation_title,
    update_conversation_title,
)

from app.db.messages import (
    get_history,
    save_message,
)

from app.db.documents import (
    check_document_exists,
    add_conversation_document,
    get_conversation_documents,
    delete_conversation_qdrant_chunks,
)

from app.db.refresh_tokens import (
    save_refresh_token,
    get_refresh_token,
    delete_refresh_token,
    delete_all_user_refresh_tokens,
)
