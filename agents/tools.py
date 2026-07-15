"""
agents/tools.py
All LangChain tool instances used across the swarm.
Initialized once at import time.
"""
import os
from langchain_tavily import TavilySearch
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
tavily_tool = TavilySearch(max_results=5, topic="general")


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


# --- Qdrant Hybrid Retriever -------------------------------------------
def build_hybrid_retriever():
    """
    Connect to an existing Qdrant collection in hybrid mode.
    Returns a LangChain retriever tool.
    Raises if the collection doesn't support hybrid search.
    """
    from langchain_qdrant import FastEmbedSparse

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
    retriever = vector_store.as_retriever(search_kwargs={"k": 5})

    def _run_retriever(query: str) -> str:
        docs = retriever.invoke(query)
        if not docs:
            return "No relevant documents found in the knowledge base."
        return "\n\n---\n\n".join(
            f"Source: {d.metadata.get('source', 'unknown')}\n{d.page_content}"
            for d in docs
        )

    return Tool(
        name="knowledge_base_search",
        func=_run_retriever,
        description=(
            "Search the private knowledge base (internal documents). "
            "Use this FIRST for any question that might be answered by internal docs. "
            "Input should be a search query string."
        ),
    )
