"""
agents/tools/retriever.py

Qdrant hybrid retriever — per-conversation document search.

Two-mode retrieval strategy:
  - GLOBAL queries (summarize, overview, key points):
      Scroll ALL chunks belonging to this conversation.
  - SPECIFIC queries (targeted questions):
      Hybrid vector search (dense + sparse) top-10.
"""
from langchain_core.tools import Tool
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode

from app.config import get_settings

settings = get_settings()

# Query intents that need the ENTIRE document, not just top-k similar chunks.
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
    """
    from langchain_qdrant import FastEmbedSparse
    from qdrant_client.models import Filter, FieldCondition, MatchValue

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
        """Scroll ALL chunks for this conversation from Qdrant."""
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
