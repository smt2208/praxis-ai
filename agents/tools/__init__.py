"""
agents/tools — All LangChain tool instances used across the multi-agent system.

Re-exports every tool so consumers can use:
    from agents.tools import tavily_tool, arxiv_tool, build_hybrid_retriever, ...

Adding a new tool:
  1. Create a new file in this package (e.g., agents/tools/mcp.py)
  2. Import and re-export it here
"""
import os

from app.config import get_settings

settings = get_settings()

# Set API keys in env (LangChain picks them up automatically)
os.environ["OPENAI_API_KEY"] = settings.openai_api_key
os.environ["TAVILY_API_KEY"] = settings.tavily_api_key

# LangSmith tracing (optional — only set if API key is configured)
if settings.langchain_api_key:
    os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2 or "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project or "praxis-ai"


# Re-export all tools for consumers
from agents.tools.web_search import tavily_tool, tavily_news_tool
from agents.tools.academic import arxiv_tool, pubmed_tool
from agents.tools.encyclopedia import wikipedia_tool
from agents.tools.retriever import build_hybrid_retriever
from agents.tools.time_utils import get_current_time_str
