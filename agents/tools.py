"""
agents/tools.py

All LangChain tool instances used across the multi-agent system.
Initialized once at import time — reused across all agent invocations.
"""
import os
import logging

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import Tool
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Set API keys in env (LangChain picks them up automatically)
os.environ["OPENAI_API_KEY"] = settings.openai_api_key
os.environ["TAVILY_API_KEY"] = settings.tavily_api_key

# LangSmith tracing (optional — only set if API key is configured)
if settings.langchain_api_key:
    os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2 or "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project or "praxis-ai"


# --- Tavily Web Search -------------------------------------------------
# Two specialized tools: general web search + dedicated news search.
# The general agent picks the right one based on the query intent.

tavily_tool = TavilySearchResults(
    max_results=5,
    topic="general",
    search_depth="advanced",        # deeper crawl for richer results
    include_raw_content=True,       # full page text, not just snippets
)

tavily_news_tool = TavilySearchResults(
    name="tavily_news_search",
    max_results=5,
    topic="news",                   # dedicated news index — much better for current events
    search_depth="advanced",
    include_raw_content=True,
    description=(
        "Search for the latest breaking news, current events, sports results, "
        "live scores, recent announcements, and real-time updates. "
        "Use this instead of general web search when the query is about "
        "recent news, today's events, or anything time-sensitive."
    ),
)


def get_current_time_str(user_tz: str = None) -> str:
    """Format current date and time localized to user's timezone if provided."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    if user_tz:
        try:
            tz = ZoneInfo(user_tz)
            now = datetime.now(tz)
            return f"{now.strftime('%A, %B %d, %Y %H:%M:%S')} ({user_tz} Time)"
        except Exception:
            pass

    now = datetime.now()
    return f"{now.strftime('%A, %B %d, %Y %H:%M:%S')}"


# --- Arxiv (academic papers) -------------------------------------------

def _search_arxiv(query: str) -> str:
    """Search arXiv academic papers safely across different SDK versions."""
    try:
        import arxiv

        if hasattr(arxiv, "Client"):
            client = arxiv.Client()
            search = arxiv.Search(query=query, max_results=3, sort_by=arxiv.SortCriterion.Relevance)
            results = list(client.results(search))
        else:
            search = arxiv.Search(query=query, max_results=3)
            results = list(search.results())

        if not results:
            return "No relevant arXiv papers found for this query."

        formatted = []
        for r in results:
            summary = r.summary.replace("\n", " ")[:1000]
            formatted.append(
                f"Title: {r.title}\n"
                f"Authors: {', '.join(a.name for a in r.authors)}\n"
                f"URL: {r.entry_id}\n"
                f"Summary: {summary}"
            )
        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        return f"arXiv search failed: {str(e)}"


arxiv_tool = Tool(
    name="arxiv_search",
    func=_search_arxiv,
    description=(
        "Search academic papers on arXiv. Use for computer science, physics, mathematics, "
        "AI, and technical engineering papers. Input should be a concise query string."
    ),
)


# --- Wikipedia (encyclopedic background) -------------------------------

def _search_wikipedia(query: str) -> str:
    """Search Wikipedia for broad background, definitions, and history."""
    try:
        import httpx

        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 3,
        }
        resp = httpx.get(url, params=params, timeout=10)
        data = resp.json()
        search_results = data.get("query", {}).get("search", [])

        if not search_results:
            return "No Wikipedia articles found."

        snippets = []
        for item in search_results:
            title = item.get("title")
            snippet = item.get("snippet", "").replace('<span class="searchmatch">', '').replace('</span>', '')
            snippets.append(f"Title: {title}\nSnippet: {snippet}")
        return "\n\n---\n\n".join(snippets)
    except Exception as e:
        return f"Wikipedia search unavailable: {str(e)}"


wikipedia_tool = Tool(
    name="wikipedia_search",
    func=_search_wikipedia,
    description=(
        "Search Wikipedia. Best for broad background, historical facts, definitions, "
        "biographies, and concepts. Input should be a search query string."
    ),
)


# --- PubMed (medical & life sciences) ----------------------------------

def _search_pubmed(query: str) -> str:
    """Search PubMed NCBI database for medical, biological, and life science papers."""
    try:
        import httpx

        esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": 3}
        resp = httpx.get(esearch_url, params=params, timeout=10)
        id_list = resp.json().get("esearchresult", {}).get("idlist", [])

        if not id_list:
            return "No PubMed medical articles found for this query."

        esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        summary_params = {"db": "pubmed", "id": ",".join(id_list), "retmode": "json"}
        sum_resp = httpx.get(esummary_url, params=summary_params, timeout=10)
        sum_data = sum_resp.json().get("result", {})

        results = []
        for pmid in id_list:
            item = sum_data.get(pmid, {})
            title = item.get("title", "No title")
            pubdate = item.get("pubdate", "")
            authors = ", ".join(a.get("name", "") for a in item.get("authors", [])[:3])
            results.append(f"Title: {title}\nPMID: {pmid}\nDate: {pubdate}\nAuthors: {authors}")
        return "\n\n---\n\n".join(results)
    except Exception as e:
        return f"PubMed search failed: {str(e)}"


pubmed_tool = Tool(
    name="pubmed_search",
    func=_search_pubmed,
    description=(
        "Search PubMed (NCBI). Best for medical, clinical, pharmaceutical, "
        "biological, and life science research papers. Input should be a search query string."
    ),
)


# --- Qdrant Hybrid Retriever (per-conversation) ------------------------

# Query intents that need the ENTIRE document, not just top-k similar chunks.
# Vector search fails for these because "summarize" has no semantically similar chunks.
_GLOBAL_INTENT_KEYWORDS = frozenset({
    "summarize", "summary", "summarise", "summarisation", "summarization",
    "overview", "brief", "explain the document", "explain the file", "explain this",
    "what is this document", "what is this file", "what does this document",
    "key points", "key takeaways", "takeaways", "highlights", "main points",
    "what is in the pdf", "what is in the file", "entire document", "whole document",
    "all sections", "table of contents", "introduction", "conclusion",
    "structure of", "outline of",
})


def _is_global_query(query: str) -> bool:
    """Return True if the query requires the full document rather than targeted chunks."""
    q = query.lower()
    return any(kw in q for kw in _GLOBAL_INTENT_KEYWORDS)


def build_hybrid_retriever(user_id: str, conversation_id: str) -> Tool:
    """
    Build a Qdrant hybrid retriever filtered to a specific conversation's documents.

    Two-mode retrieval strategy:
    - GLOBAL queries (summarize, overview, key points, etc.):
        Scroll ALL chunks belonging to this conversation → gives full-doc context.
    - SPECIFIC queries (targeted questions about facts, dates, names, etc.):
        Hybrid vector search (dense + sparse) top-10 → fast and precise.

    The filter is applied at the Qdrant level, so only chunks where
    metadata.conversation_id == conversation_id are ever returned.
    """
    from langchain_qdrant import FastEmbedSparse
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    # Match both root payload keys and metadata-nested payload keys
    user_filter = Filter(
        should=[
            Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="conversation_id", match=MatchValue(value=conversation_id)),
                ]
            ),
            Filter(
                must=[
                    FieldCondition(key="metadata.user_id", match=MatchValue(value=user_id)),
                    FieldCondition(key="metadata.conversation_id", match=MatchValue(value=conversation_id)),
                ]
            ),
        ]
    )

    try:
        vector_store = QdrantVectorStore.from_existing_collection(
            embedding=OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=settings.openai_api_key,
            ),
            sparse_embedding=FastEmbedSparse(model_name="Qdrant/bm25"),
            collection_name=settings.qdrant_collection_name,
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            retrieval_mode=RetrievalMode.HYBRID,
            vector_name="dense",
            sparse_vector_name="sparse",
        )
        retriever = vector_store.as_retriever(
            search_kwargs={"k": 10, "filter": user_filter}
        )
        qdrant_client = vector_store.client
    except Exception as exc:
        error_text = str(exc)

        def _unavailable(_: str) -> str:
            return f"Knowledge base retrieval is unavailable: Could not connect to Qdrant collection: {error_text}"

        return Tool(
            name="knowledge_base_search",
            func=_unavailable,
            description="Search your private documents. Input should be a search query string.",
        )

    def _fetch_all_chunks() -> list:
        """Scroll ALL chunks for this conversation from Qdrant (for global queries)."""
        all_chunks = []
        offset = None
        while True:
            results, offset = qdrant_client.scroll(
                collection_name=settings.qdrant_collection_name,
                scroll_filter=user_filter,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            all_chunks.extend(results)
            if offset is None:
                break
        return all_chunks

    def _run_retriever(query: str) -> str:
        if _is_global_query(query):
            raw_chunks = _fetch_all_chunks()
            if not raw_chunks:
                return "No documents found in your knowledge base for this conversation."

            raw_chunks.sort(key=lambda p: (
                p.payload.get("metadata", {}).get("page", p.payload.get("page", 0))
            ))

            parts = []
            for point in raw_chunks:
                payload = point.payload
                meta = payload.get("metadata", payload)
                source = meta.get("source", "unknown").split("/")[-1].split("\\")[-1]
                page = meta.get("page", "?")
                text = payload.get("page_content", "")
                if text.strip():
                    parts.append(f"[Source: {source} | Page {page}]\n{text}")

            return "\n\n---\n\n".join(parts)
        else:
            docs = retriever.invoke(query)
            if not docs:
                return "No relevant documents found in your knowledge base."
            return "\n\n---\n\n".join(
                f"Source: {d.metadata.get('source', 'unknown')} (page {d.metadata.get('page', '?')})\n{d.page_content}"
                for d in docs
            )

    return Tool(
        name="knowledge_base_search",
        func=_run_retriever,
        description=(
            "Search the user's private uploaded documents. "
            "Use this for any question about documents the user has uploaded. "
            "Input should be a search query string."
        ),
    )
