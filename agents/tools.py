"""
agents/tools.py
All LangChain tool instances used across the multi-agent system.
Initialized once at import time.
"""
import os
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import Tool
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode

from app.config import get_settings

settings = get_settings()

# Set API keys in env (langchain picks them up automatically)
os.environ["OPENAI_API_KEY"] = settings.openai_api_key
os.environ["TAVILY_API_KEY"] = settings.tavily_api_key


# --- Tavily (general web + news) ----------------------------------------
tavily_tool = TavilySearchResults(max_results=5, topic="general")


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


# --- Qdrant Hybrid Retriever (per-user) --------------------------------

def build_hybrid_retriever(user_id: str, conversation_id: str) -> Tool:
    """
    Build a Qdrant hybrid retriever filtered to a specific conversation's documents.

    The filter is applied at the Qdrant level (not post-processing),
    so only chunks where metadata.conversation_id == conversation_id are ever returned.
    We also require user_id as an extra security layer.
    """
    from langchain_qdrant import FastEmbedSparse
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    # Match both root payload keys and metadata nested payload keys (langchain_qdrant payload structure)
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
            search_kwargs={"k": 5, "filter": user_filter}
        )
    except Exception as exc:
        error_text = str(exc)

        def _unavailable(_: str) -> str:
            return (
                "Knowledge base retrieval is unavailable: "
                f"Could not connect to Qdrant collection: {error_text}"
            )

        return Tool(
            name="knowledge_base_search",
            func=_unavailable,
            description="Search your private documents. Input should be a search query string.",
        )

    def _run_retriever(query: str) -> str:
        docs = retriever.invoke(query)
        
        # Smart Summarization Fallback: If user asks for summary/overview and specific query yields sparse results,
        # fallback to pulling broad structural chunks (e.g. introduction, main findings, page 1-3).
        summary_keywords = ["summarize", "summary", "overview", "key points", "main findings", "about", "explain the doc"]
        if (not docs or len(docs) < 2) and any(k in query.lower() for k in summary_keywords):
            fallback_docs = retriever.invoke("introduction overview main points summary conclusion section 1")
            if fallback_docs:
                docs = fallback_docs

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

