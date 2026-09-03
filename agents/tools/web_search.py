"""
agents/tools/web_search.py

OpenAI-native web search tools using OpenAI's built-in web search tool
with the fast model (FAST_MODEL = "gpt-5.4-nano").

Replaces Tavily with OpenAI's official web search for superior factual
grounding, high-speed citations, and real-time live retrieval.
"""
import logging
from typing import Optional

from openai import OpenAI, AsyncOpenAI
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.config import get_settings, FAST_MODEL

logger = logging.getLogger(__name__)
settings = get_settings()

# Cached client instances for HTTP connection reuse
_sync_client: Optional[OpenAI] = None
_async_client: Optional[AsyncOpenAI] = None


def _get_sync_client() -> OpenAI:
    global _sync_client
    if _sync_client is None:
        _sync_client = OpenAI(api_key=settings.openai_api_key)
    return _sync_client


def _get_async_client() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _async_client


class SearchQueryInput(BaseModel):
    query: str = Field(description="The search query or topic to look up on the web.")


def _run_openai_search_sync(query: str, is_news: bool = False) -> str:
    """Execute synchronous web search via OpenAI Responses API using FAST_MODEL."""
    client = _get_sync_client()
    search_prompt = f"Find recent breaking news, live results, and latest developments for: {query}" if is_news else query

    try:
        response = client.responses.create(
            model=FAST_MODEL,
            tools=[{"type": "web_search"}],
            input=search_prompt,
        )
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text.strip()
        elif hasattr(response, "output") and response.output:
            parts = []
            for item in response.output:
                if hasattr(item, "content") and item.content:
                    parts.append(str(item.content))
                elif hasattr(item, "text") and item.text:
                    parts.append(str(item.text))
            if parts:
                return "\n\n".join(parts).strip()
    except Exception as exc:
        logger.warning(
            "[OpenAI WebSearch] Responses API call failed with %s: %s. Using Chat Completions fallback.",
            FAST_MODEL,
            exc,
        )

    # Fallback to chat completions if responses API has issues
    try:
        completion = client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert real-time web search engine. "
                        "Provide the most accurate, up-to-date facts, dates, news, and details."
                    ),
                },
                {"role": "user", "content": search_prompt},
            ],
        )
        return completion.choices[0].message.content or "No search results returned."
    except Exception as exc2:
        logger.error("[OpenAI WebSearch] Search fallback failed: %s", exc2)
        return f"Error executing web search: {exc2}"


async def _run_openai_search_async(query: str, is_news: bool = False) -> str:
    """Execute asynchronous web search via OpenAI Responses API using FAST_MODEL."""
    client = _get_async_client()
    search_prompt = f"Find recent breaking news, live results, and latest developments for: {query}" if is_news else query

    try:
        response = await client.responses.create(
            model=FAST_MODEL,
            tools=[{"type": "web_search"}],
            input=search_prompt,
        )
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text.strip()
        elif hasattr(response, "output") and response.output:
            parts = []
            for item in response.output:
                if hasattr(item, "content") and item.content:
                    parts.append(str(item.content))
                elif hasattr(item, "text") and item.text:
                    parts.append(str(item.text))
            if parts:
                return "\n\n".join(parts).strip()
    except Exception as exc:
        logger.warning(
            "[OpenAI WebSearch] Async Responses API call failed with %s: %s. Using Chat Completions fallback.",
            FAST_MODEL,
            exc,
        )

    # Fallback to chat completions
    try:
        completion = await client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert real-time web search engine. "
                        "Provide the most accurate, up-to-date facts, dates, news, and details."
                    ),
                },
                {"role": "user", "content": search_prompt},
            ],
        )
        return completion.choices[0].message.content or "No search results returned."
    except Exception as exc2:
        logger.error("[OpenAI WebSearch] Async search fallback failed: %s", exc2)
        return f"Error executing web search: {exc2}"


# --- LangChain Tools ---------------------------------------------------

def _general_search_sync(query: str) -> str:
    return _run_openai_search_sync(query, is_news=False)


async def _general_search_async(query: str) -> str:
    return await _run_openai_search_async(query, is_news=False)


def _news_search_sync(query: str) -> str:
    return _run_openai_search_sync(query, is_news=True)


async def _news_search_async(query: str) -> str:
    return await _run_openai_search_async(query, is_news=True)


openai_web_search = StructuredTool.from_function(
    func=_general_search_sync,
    coroutine=_general_search_async,
    name="openai_web_search",
    description=(
        "Search the web for real-time information, current events, recent developments, "
        "technical documentation, product info, and general knowledge using OpenAI Web Search."
    ),
    args_schema=SearchQueryInput,
)

openai_news_search = StructuredTool.from_function(
    func=_news_search_sync,
    coroutine=_news_search_async,
    name="openai_news_search",
    description=(
        "Search for breaking news, current events, sports scores, market results, "
        "live announcements, and real-time updates using OpenAI Web Search. "
        "Use this instead of general search when the query is time-sensitive or about recent news."
    ),
    args_schema=SearchQueryInput,
)

# Backwards compatibility aliases for any legacy references
tavily_tool = openai_web_search
tavily_news_tool = openai_news_search
