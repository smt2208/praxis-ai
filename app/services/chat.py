"""
app/services/chat.py

Chat business logic extracted from the HTTP router.
"""
import asyncio
import logging

import asyncpg
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import DEFAULT_MODEL
from app.db.conversations import update_conversation_title

logger = logging.getLogger(__name__)


async def auto_generate_title(pool: asyncpg.Pool, conversation_id: str, first_message: str) -> None:
    """Background task to generate a descriptive 3-5 word title like ChatGPT/Claude."""
    try:
        title_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.5)
        response = await asyncio.to_thread(
            title_llm.invoke,
            [
                SystemMessage(content="Create a concise, 3-5 word title summarizing the user's prompt. Do NOT use quotes or trailing punctuation. Keep it short like a ChatGPT sidebar title."),
                HumanMessage(content=first_message),
            ]
        )
        new_title = response.content.strip().strip('"').strip("'")
        if new_title:
            await update_conversation_title(pool, conversation_id, new_title)
    except Exception as e:
        logger.warning("[auto-title] Could not auto-title conversation: %s", e)
