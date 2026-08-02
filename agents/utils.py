"""
agents/utils.py

Shared utilities used across all agent subgraphs.
Keeps agent modules DRY without introducing unnecessary abstractions.
"""
from langchain_core.messages import BaseMessage


def format_history(history: list, last_n: int = 4) -> str:
    """
    Format a list of messages (dicts or BaseMessage objects) into a compact
    text summary for injection into LLM prompts.

    Args:
        history: List of message dicts ({"role": ..., "content": ...})
                 or LangChain BaseMessage objects.
        last_n:  Number of most recent messages to include. Keeps prompts
                 focused and within token budgets.

    Returns:
        A newline-joined string like "USER: ...\nASSISTANT: ..."
        or empty string if history is empty.
    """
    if not history:
        return ""

    formatted = []
    for m in history[-last_n:]:
        if isinstance(m, dict):
            role = m.get("role", "user").upper()
            content = m.get("content", "")
        else:
            role = getattr(m, "type", "human").upper()
            content = getattr(m, "content", "")
        if content:
            formatted.append(f"{role}: {content}")

    return "\n".join(formatted)


def build_doc_context(has_documents: bool) -> str:
    """
    Build the document-awareness context string injected into the CEO router prompt.

    Single source of truth — used by both sync invoke and SSE streaming paths
    so routing decisions are always consistent.
    """
    if has_documents:
        return (
            "CONTEXT: The user has attached document(s) to this chat session. "
            "Route to `knowledge_team` ONLY IF the user's question asks about, "
            "summarizes, extracts from, or references the contents of the uploaded files. "
            "For general questions, news, coding, math, or web search queries that do NOT "
            "depend on the uploaded files, route to `general` or `research_team`."
        )
    return "CONTEXT: No documents are attached to this conversation. Do NOT route to `knowledge_team`."


def build_image_context(has_images: bool, count: int = 0) -> str:
    """Build the image-awareness context string injected into the CEO router prompt."""
    if has_images:
        return (
            f"IMAGE CONTEXT: The user has attached {count} image(s) to this message. "
            "Route to `vision_agent` for visual analysis, image description, diagram understanding, or OCR."
        )
    return "IMAGE CONTEXT: No images are attached to this message."


def build_user_profile_context(user_row: dict | None) -> str:
    """Format user profile metadata (name, age, profession, location) into prompt context."""
    if not user_row:
        return ""

    parts = []
    if user_row.get("full_name"):
        parts.append(f"Name: {user_row['full_name']}")
    if user_row.get("age"):
        parts.append(f"Age: {user_row['age']}")
    if user_row.get("profession"):
        parts.append(f"Profession: {user_row['profession']}")

    location_items = [user_row.get(k) for k in ("city", "state", "country") if user_row.get(k)]
    if location_items:
        parts.append(f"Location: {', '.join(location_items)}")

    if not parts:
        return ""

    return "User Profile Details:\n" + "\n".join(f"- {p}" for p in parts)

