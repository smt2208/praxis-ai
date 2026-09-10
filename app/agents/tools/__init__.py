"""
app/agents/tools — All LangChain tool instances used across the multi-agent system.

Re-exports every tool so consumers can use:
    from app.agents.tools import openai_web_search, arxiv_tool, build_hybrid_retriever, ...

Adding a new tool:
  1. Create a new file in this package (e.g., app/agents/tools/my_tool.py)
  2. Import and re-export it here
"""

from app.agents.tools.web_search import (
    openai_web_search,
    openai_news_search,
)
from app.agents.tools.academic import arxiv_tool, pubmed_tool
from app.agents.tools.encyclopedia import wikipedia_tool
from app.agents.tools.retriever import build_hybrid_retriever
from app.agents.tools.time_utils import get_current_time_str

__all__ = [
    "openai_web_search",
    "openai_news_search",
    "arxiv_tool",
    "pubmed_tool",
    "wikipedia_tool",
    "build_hybrid_retriever",
    "get_current_time_str",
]

