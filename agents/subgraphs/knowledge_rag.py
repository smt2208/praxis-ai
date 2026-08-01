"""
agents/subgraphs/knowledge_rag.py

RAG helper utilities for the Knowledge Team:
  - rewrite_query:        Converts a conversational query into a standalone search query
  - evaluate_doc_context: Decides whether retrieved chunks are sufficient to answer

These are extracted from knowledge_team.py so they are independently testable
and importable without pulling in the full LangGraph graph.
"""
import logging

from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from app.config import DEFAULT_MODEL

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


# ---------------------------------------------------------------------------
# Query Rewriting
# ---------------------------------------------------------------------------

@traceable(name="Rewrite Query", run_type="chain")
def rewrite_query(query: str, history_summary: str = "") -> str:
    """
    Rewrite a conversational user query into an explicit, standalone vector
    search query that is self-contained without needing chat history.
    Returns the original query unchanged if rewriting fails or is unnecessary.
    """
    if not history_summary:
        return query

    from prompts.knowledge_prompts import QUERY_REWRITER_SYSTEM
    prompt = f"Chat History:\n{history_summary}\n\nLatest User Query: {query}"
    try:
        response = _llm.invoke([
            SystemMessage(content=QUERY_REWRITER_SYSTEM),
            HumanMessage(content=prompt),
        ])
        rewritten = response.content.strip()
        return rewritten if rewritten else query
    except Exception:
        return query


# ---------------------------------------------------------------------------
# Document Context Evaluation
# ---------------------------------------------------------------------------

class EvaluationResult(BaseModel):
    sufficient: bool
    reason: str


_evaluator_llm = _llm.with_structured_output(EvaluationResult)


@traceable(name="Evaluate Doc Context", run_type="chain")
def evaluate_doc_context(query: str, rag_results: str) -> bool:
    """
    Determine if retrieved document context is sufficient to answer the query.
    Returns True if web search can be skipped, False if additional search is needed.
    """
    if not rag_results or len(rag_results.strip()) < 20:
        return False

    from prompts.knowledge_prompts import EVALUATOR_SYSTEM
    try:
        result = _evaluator_llm.invoke([
            SystemMessage(content=EVALUATOR_SYSTEM),
            HumanMessage(content=f"Query: {query}\n\nRetrieved Document Context:\n{rag_results}"),
        ])
        return result.sufficient
    except Exception:
        return True  # Assume sufficient on error (avoids unnecessary web search)
