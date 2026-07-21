"""
agents/tools.py
All LangChain tool instances used across the swarm.
Initialized once at import time.
"""
import os
from langchain_tavily import TavilySearchResults
from langchain_community.utilities import ArxivAPIWrapper
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


# --- Arxiv (academic papers) -------------------------------------------
_arxiv_wrapper = ArxivAPIWrapper(top_k_results=3, doc_content_chars_max=4000)
arxiv_tool = Tool(
    name="arxiv_search",
    func=_arxiv_wrapper.run,
    description=(
        "Search academic papers on arXiv. Use for scientific, technical, "
        "or research-heavy questions. Input should be a search query string."
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

    # Only return documents that belong to this user AND this specific conversation
    user_filter = Filter(
        must=[
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            FieldCondition(key="conversation_id", match=MatchValue(value=conversation_id))
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

