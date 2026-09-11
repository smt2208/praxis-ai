"""
app/agents/tools/web_search.py

Dedicated Web Search Agent implemented as a reusable LangGraph subgraph.

Orchestrates three specialized search engines:
  - Firecrawl (langchain-firecrawl): Live, current, latest, breaking news, and page extraction.
  - Tavily (langchain-tavily): General-purpose web search, facts, and Q&A.
  - Exa (langchain-exa): Neural semantic search, academic, and deep-dive technical research.

The subgraph:
  1. router_node: Uses an LLM classifier to select the optimal search provider based on
     the query intent and configured API keys.
  2. search_node: Executes the primary provider using LangChain's official integration,
     with automatic multi-provider fallback if an API is unavailable or rate-limited.
  3. synthesize_node: Deduplicates, ranks, and formats results into clean, citation-ready
     markdown with source URLs.

Exposed as a single unified `web_search_tool` to downstream teams and agents.
"""
import logging
import re
from typing import TypedDict

import httpx
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langsmith import traceable
from pydantic import BaseModel, Field

from app.config import FAST_MODEL, get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_llm_router = ChatOpenAI(model=FAST_MODEL, temperature=0)


# ---------------------------------------------------------------------------
# State & Data Structures
# ---------------------------------------------------------------------------

class SearchQueryInput(BaseModel):
    query: str = Field(description="The search query or topic to look up on the web.")


class SearchResultItem(TypedDict):
    title: str
    url: str
    snippet: str
    provider: str


class WebSearchState(TypedDict):
    query: str
    preferred_provider: str
    active_provider: str
    fallback_providers: list[str]
    results: list[SearchResultItem]
    formatted_output: str


# ---------------------------------------------------------------------------
# Provider Execution Handlers (LangChain Partners with HTTP Fallback)
# ---------------------------------------------------------------------------

async def _search_firecrawl(query: str, api_key: str) -> list[SearchResultItem]:
    """Execute search via Firecrawl (LangChain partner tool with direct HTTP fallback)."""
    # Attempt official LangChain partner tool
    try:
        from langchain_firecrawl import FirecrawlSearch

        tool = FirecrawlSearch(api_key=api_key)
        raw = await tool.ainvoke({"query": query})
        items: list[SearchResultItem] = []
        if isinstance(raw, list):
            for doc in raw[:5]:
                title = getattr(doc, "metadata", {}).get("title") or getattr(doc, "title", "Firecrawl Source")
                url = getattr(doc, "metadata", {}).get("url") or getattr(doc, "url", "")
                content = getattr(doc, "page_content", "") or str(doc)
                items.append({
                    "title": str(title).strip(),
                    "url": str(url).strip(),
                    "snippet": content[:800].strip(),
                    "provider": "firecrawl",
                })
        elif isinstance(raw, dict) and "data" in raw:
            for d in raw.get("data", [])[:5]:
                items.append({
                    "title": d.get("title") or d.get("metadata", {}).get("title", "Firecrawl Source"),
                    "url": d.get("url", ""),
                    "snippet": (d.get("markdown") or d.get("description") or "")[:800].strip(),
                    "provider": "firecrawl",
                })
        if items:
            return items
    except Exception as exc:
        logger.debug("[WebSearch] langchain-firecrawl invocation failed or not loaded: %s. Using HTTP fallback.", exc)

    # HTTP Fallback (v1 /search)
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.post(
            "https://api.firecrawl.dev/v1/search",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"query": query, "limit": 5, "scrapeOptions": {"formats": ["markdown"]}},
        )
        resp.raise_for_status()
        data = resp.json()
        results_data = data.get("data", []) if isinstance(data, dict) else []
        items = []
        for d in results_data:
            url = d.get("url", "")
            title = d.get("title") or d.get("metadata", {}).get("title", "Source")
            snippet = d.get("markdown") or d.get("description") or ""
            items.append({
                "title": str(title).strip(),
                "url": str(url).strip(),
                "snippet": str(snippet)[:800].strip(),
                "provider": "firecrawl",
            })
        return items


async def _search_tavily(query: str, api_key: str) -> list[SearchResultItem]:
    """Execute search via Tavily (LangChain partner tool with direct HTTP fallback)."""
    try:
        from langchain_tavily import TavilySearch

        tool = TavilySearch(max_results=5, tavily_api_key=api_key)
        raw = await tool.ainvoke({"query": query})
        items: list[SearchResultItem] = []
        if isinstance(raw, dict) and "results" in raw:
            for r in raw.get("results", [])[:5]:
                items.append({
                    "title": r.get("title", "Tavily Source"),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:800].strip(),
                    "provider": "tavily",
                })
        elif isinstance(raw, list):
            for r in raw[:5]:
                if isinstance(r, dict):
                    items.append({
                        "title": r.get("title", "Tavily Source"),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", "")[:800].strip(),
                        "provider": "tavily",
                    })
        if items:
            return items
    except Exception as exc:
        logger.debug("[WebSearch] langchain-tavily invocation failed or not loaded: %s. Using HTTP fallback.", exc)

    # HTTP Fallback
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={"api_key": api_key, "query": query, "max_results": 5, "include_answer": True},
        )
        resp.raise_for_status()
        data = resp.json()
        items = []
        for r in data.get("results", [])[:5]:
            items.append({
                "title": r.get("title", "Tavily Source"),
                "url": r.get("url", ""),
                "snippet": r.get("content", "")[:800].strip(),
                "provider": "tavily",
            })
        return items


async def _search_exa(query: str, api_key: str) -> list[SearchResultItem]:
    """Execute search via Exa (LangChain partner tool with direct HTTP fallback)."""
    try:
        from langchain_exa import ExaSearchResults

        tool = ExaSearchResults(exa_api_key=api_key)
        raw = await tool.ainvoke({"query": query, "num_results": 5})
        items: list[SearchResultItem] = []
        if isinstance(raw, list):
            for doc in raw[:5]:
                title = getattr(doc, "metadata", {}).get("title") or getattr(doc, "title", "Exa Source")
                url = getattr(doc, "metadata", {}).get("url") or getattr(doc, "url", "")
                snippet = getattr(doc, "page_content", "") or str(doc)
                items.append({
                    "title": str(title).strip(),
                    "url": str(url).strip(),
                    "snippet": str(snippet)[:800].strip(),
                    "provider": "exa",
                })
        elif isinstance(raw, dict) and "results" in raw:
            for r in raw.get("results", [])[:5]:
                items.append({
                    "title": r.get("title", "Exa Source"),
                    "url": r.get("url", ""),
                    "snippet": (r.get("text") or r.get("snippet") or "")[:800].strip(),
                    "provider": "exa",
                })
        if items:
            return items
    except Exception as exc:
        logger.debug("[WebSearch] langchain-exa invocation failed or not loaded: %s. Using HTTP fallback.", exc)

    # HTTP Fallback
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={"query": query, "numResults": 5, "contents": {"text": {"maxCharacters": 1500}}},
        )
        resp.raise_for_status()
        data = resp.json()
        items = []
        for r in data.get("results", [])[:5]:
            items.append({
                "title": r.get("title", "Exa Source"),
                "url": r.get("url", ""),
                "snippet": (r.get("text") or "")[:800].strip(),
                "provider": "exa",
            })
        return items


# ---------------------------------------------------------------------------
# LangGraph Subgraph Nodes
# ---------------------------------------------------------------------------

ROUTER_PROMPT = """You are an intelligent Web Search Routing Specialist for a multi-agent AI system.
Select the SINGLE best search provider for the user's query:

- "firecrawl": Prioritize for live, current, latest, breaking news, sports, weather, stock/crypto prices, real-time events, or fresh page scraping.
- "exa": Prioritize for deep research, academic, scientific, architecture, algorithms, or semantic technical exploration.
- "tavily": Prioritize for general web search, factual overviews, tutorials, product documentation, comparisons, or everyday queries.

Configured available providers: {available_providers}

Query: "{query}"

Output ONLY one word: "firecrawl", "tavily", or "exa"."""


@traceable(name="Web Search Router Node", run_type="chain")
async def router_node(state: WebSearchState) -> dict:
    """Analyze query intent and select the appropriate search provider based on available keys."""
    available_keys: dict[str, str] = {}
    if settings.firecrawl_api_key:
        available_keys["firecrawl"] = settings.firecrawl_api_key
    if settings.tavily_api_key:
        available_keys["tavily"] = settings.tavily_api_key
    if settings.exa_api_key:
        available_keys["exa"] = settings.exa_api_key

    # If only one provider is configured, route directly to it
    if len(available_keys) == 1:
        chosen = next(iter(available_keys))
        return {
            "preferred_provider": chosen,
            "active_provider": chosen,
            "fallback_providers": [],
        }

    # If no provider keys configured, record empty
    if not available_keys:
        return {
            "preferred_provider": "none",
            "active_provider": "none",
            "fallback_providers": [],
        }

    # Fast heuristic check before calling LLM
    q_lower = state["query"].lower()
    is_time_sensitive = bool(
        re.search(
            r"\b(today|yesterday|latest|breaking|live|current|now|price|score|weather|news|update|202[5-9])\b",
            q_lower,
        )
    )
    is_deep_research = bool(
        re.search(
            r"\b(paper|benchmark|architecture|algorithm|deep dive|methodology|neural|state-of-the-art|sota)\b",
            q_lower,
        )
    )

    if is_time_sensitive and "firecrawl" in available_keys:
        chosen = "firecrawl"
    elif is_deep_research and "exa" in available_keys:
        chosen = "exa"
    else:
        # Ask LLM router to classify between available providers
        try:
            prompt = ROUTER_PROMPT.format(
                available_providers=", ".join(available_keys.keys()),
                query=state["query"],
            )
            response = await _llm_router.ainvoke([SystemMessage(content=prompt)])
            decision = (response.content if isinstance(response.content, str) else "").strip().lower()
            chosen = decision if decision in available_keys else next(iter(available_keys))
        except Exception as exc:
            logger.warning("[WebSearch Router] LLM classification failed (%s), defaulting to available provider.", exc)
            chosen = "tavily" if "tavily" in available_keys else next(iter(available_keys))

    # Form ordered fallbacks (all available providers except chosen)
    fallbacks = [p for p in available_keys if p != chosen]

    logger.info("[WebSearch Router] Selected '%s' (fallbacks: %s) for query: '%s'", chosen, fallbacks, state["query"])
    return {
        "preferred_provider": chosen,
        "active_provider": chosen,
        "fallback_providers": fallbacks,
    }


@traceable(name="Web Search Execution Node", run_type="chain")
async def search_node(state: WebSearchState) -> dict:
    """Execute search against active provider with automatic fallback to alternates on failure."""
    active = state.get("active_provider", "none")
    fallbacks = list(state.get("fallback_providers", []))
    providers_to_try = [active] + fallbacks if active != "none" else []

    provider_funcs = {
        "firecrawl": lambda q: _search_firecrawl(q, settings.firecrawl_api_key),
        "tavily": lambda q: _search_tavily(q, settings.tavily_api_key),
        "exa": lambda q: _search_exa(q, settings.exa_api_key),
    }

    all_results: list[SearchResultItem] = []
    used_provider = "none"

    for provider in providers_to_try:
        if provider not in provider_funcs:
            continue
        try:
            logger.info("[WebSearch] Invoking provider '%s' for query: '%s'", provider, state["query"])
            items = await provider_funcs[provider](state["query"])
            if items:
                all_results = items
                used_provider = provider
                break
            else:
                logger.warning("[WebSearch] Provider '%s' returned 0 results for '%s'. Trying next.", provider, state["query"])
        except Exception as exc:
            logger.warning("[WebSearch] Provider '%s' failed: %s. Trying next provider.", provider, exc)

    return {"results": all_results, "active_provider": used_provider}


@traceable(name="Web Search Synthesize Node", run_type="chain")
async def synthesize_node(state: WebSearchState) -> dict:
    """Deduplicate, rank, and format search results into clean, citation-ready output."""
    raw_results = state.get("results", [])
    provider = state.get("active_provider", "unknown")

    if not raw_results:
        configured = [p for p in ("FIRECRAWL_API_KEY", "TAVILY_API_KEY", "EXA_API_KEY") if getattr(settings, p.lower(), None)]
        if not configured:
            msg = (
                "Web search is currently unconfigured. Please provide FIRECRAWL_API_KEY, "
                "TAVILY_API_KEY, or EXA_API_KEY in the environment."
            )
        else:
            msg = f"No relevant web search results found for query: '{state['query']}'."
        return {"formatted_output": msg}

    # Deduplicate by URL
    seen_urls: set[str] = set()
    deduped: list[SearchResultItem] = []
    for item in raw_results:
        url = item.get("url", "").rstrip("/")
        if not url or url not in seen_urls:
            if url:
                seen_urls.add(url)
            deduped.append(item)

    # Format into concise, citation-ready text
    formatted_blocks: list[str] = []
    for idx, item in enumerate(deduped[:5], 1):
        title = item.get("title") or f"Source {idx}"
        url = item.get("url") or ""
        snippet = item.get("snippet", "")
        formatted_blocks.append(
            f"{idx}. **[{title}]({url})**\n   {snippet}"
        )

    formatted_output = (
        f"### Web Search Results ({provider.capitalize()}):\n\n"
        + "\n\n".join(formatted_blocks)
    )

    return {"formatted_output": formatted_output}


# ---------------------------------------------------------------------------
# Subgraph Assembly & Compilation
# ---------------------------------------------------------------------------

def _build_web_search_graph():
    """Compile the Web Search LangGraph subgraph."""
    builder = StateGraph(WebSearchState)

    builder.add_node("router", router_node)
    builder.add_node("search", search_node)
    builder.add_node("synthesize", synthesize_node)

    builder.add_edge(START, "router")
    builder.add_edge("router", "search")
    builder.add_edge("search", "synthesize")
    builder.add_edge("synthesize", END)

    return builder.compile()


_web_search_graph = _build_web_search_graph()


# ---------------------------------------------------------------------------
# Public Tool Interfaces
# ---------------------------------------------------------------------------

async def _run_web_search_async(query: str) -> str:
    """Execute asynchronous query against the LangGraph Web Search Subgraph."""
    try:
        final_state = await _web_search_graph.ainvoke({"query": query})
        return final_state.get("formatted_output", "No search results returned.")
    except Exception as exc:
        logger.error("[WebSearch] Subgraph execution failed: %s", exc)
        return f"Web search failed: {exc}"


web_search_tool = StructuredTool.from_function(
    coroutine=_run_web_search_async,
    name="web_search",
    description=(
        "Intelligent multi-provider web search engine powered by Firecrawl, Tavily, and Exa. "
        "Retrieves real-time facts, breaking news, live results, technical documentation, and deep research. "
        "Returns clean, citation-ready summaries with source URLs. Input must be a search query string."
    ),
    args_schema=SearchQueryInput,
)
