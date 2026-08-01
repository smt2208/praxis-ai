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
