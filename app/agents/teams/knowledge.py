"""
app/agents/teams/knowledge.py

Enterprise Document RAG & CRAG Specialist Department.
Consolidates:
  - Query rewriting & relevance evaluation (CRAG helpers)
  - Multi-query expansion & RRF fusion
  - Real-time SSE streaming runner (astream_knowledge_team)
"""
import asyncio
import logging
import re

from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent
from langsmith import traceable

from app.config import DEFAULT_MODEL, FAST_MODEL
from app.agents.context import format_history
from app.agents.tools import openai_web_search, build_hybrid_retriever
from app.agents.prompts.knowledge import (
    SYNTHESIZER_SYSTEM,
    SYNTHESIZER_HUMAN,
    QUERY_REWRITER_SYSTEM,
    EVALUATOR_SYSTEM,
)

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)
_fast_llm = ChatOpenAI(model=FAST_MODEL, temperature=0)


# ---------------------------------------------------------------------------
# CRAG Evaluation Schema
# ---------------------------------------------------------------------------

class EvaluationResult(BaseModel):
    sufficient: bool
    reason: str


_evaluator_llm = _llm.with_structured_output(EvaluationResult)


# ---------------------------------------------------------------------------
# CRAG Helper Utilities
# ---------------------------------------------------------------------------

@traceable(name="Rewrite Query", run_type="chain")
async def rewrite_query(query: str, history_summary: str = "") -> str:
    """
    Rewrite a conversational user query into an explicit, standalone vector
    search query that is self-contained without needing chat history.
    Returns the original query unchanged if rewriting fails or is unnecessary.
    """
    if not history_summary:
        return query

    prompt = f"Chat History:\n{history_summary}\n\nLatest User Query: {query}"
    try:
        response = await _llm.ainvoke([
            SystemMessage(content=QUERY_REWRITER_SYSTEM),
            HumanMessage(content=prompt),
        ])
        rewritten = response.content.strip()
        return rewritten if rewritten else query
    except Exception:
        return query


@traceable(name="Evaluate Doc Context", run_type="chain")
async def evaluate_doc_context(query: str, doc_context: str) -> bool:
    """
    Decide whether the retrieved document chunks contain enough information
    to fully answer the query. Returns True if sufficient, False if web search fallback needed.
    """
    if not doc_context or len(doc_context.strip()) < 50:
        return False

    prompt = f"User Query: {query}\n\nRetrieved Document Chunks:\n{doc_context[:4000]}"
    try:
        result = await _evaluator_llm.ainvoke([
            SystemMessage(content=EVALUATOR_SYSTEM),
            HumanMessage(content=prompt),
        ])
        return result.sufficient
    except Exception:
        return True


async def _expand_queries(query: str) -> list[str]:
    """
    Generate 2 complementary search query variants for improved retrieval recall.
    Falls back to the original query if expansion fails.
    """
    prompt = (
        f"Generate exactly 2 alternative search queries for the following question. "
        f"Return them as a Python list of strings (e.g. [\"query1\", \"query2\"]). "
        f"Make them semantically distinct: one specific/technical, one conceptual/broad.\n\n"
        f"Original question: {query}"
    )
    try:
        response = await _fast_llm.ainvoke([HumanMessage(content=prompt)])
        text = response.content.strip()
        found = re.findall(r'"([^"]+)"', text)
        queries = [q.strip() for q in found if q.strip()]
        if len(queries) >= 2:
            return [query] + queries[:2]   # original + 2 variants
    except Exception as exc:
        logger.debug("[KnowledgeTeam] Query expansion failed (using original): %s", exc)
    return [query]


def _rrf_merge(result_sets: list[str]) -> str:
    """Merge multiple retrieval result strings into one deduplicated context."""
    seen: set[str] = set()
    merged: list[str] = []
    for result in result_sets:
        for chunk in result.split("\n\n"):
            chunk = chunk.strip()
            if chunk and chunk not in seen:
                seen.add(chunk)
                merged.append(chunk)
    return "\n\n".join(merged)


# ---------------------------------------------------------------------------
# Public Streaming Execution API
# ---------------------------------------------------------------------------

@traceable(name="Knowledge Team Stream", run_type="chain")
async def astream_knowledge_team(
    query: str,
    user_id: str,
    conversation_id: str,
    history: list | None = None,
    collect_context: bool = False,
):
    """
    Enterprise RAG streaming with Corrective RAG (CRAG) verification.

    Workflow:
      1. Query Rewriting: Decontextualizes conversational pronouns against chat history.
      2. Multi-Query Expansion & Fusion: Generates 2 semantic query variants and retrieves
         document chunks concurrently via asyncio.gather, deduplicating via RRF merge.
      3. Sufficiency Evaluation: An evaluator LLM determines if document context is sufficient.
         If insufficient or missing, automatically triggers web search fallback.
      4. Grounded Synthesis: Streams answer tokens in real-time with document source citations.
    """
    history_summary = format_history(history)

    # Step 1: Query rewriting
    yield {"type": "status", "message": "Analyzing query..."}
    standalone_query = await rewrite_query(query, history_summary)

    # Step 2: CRAG — Multi-query expansion
    yield {"type": "status", "message": "Searching documents..."}
    expanded_queries = await _expand_queries(standalone_query)
    logger.info("[KnowledgeTeam] Expanded to %d queries: %s", len(expanded_queries), expanded_queries)

    rag_tool = build_hybrid_retriever(user_id=user_id, conversation_id=conversation_id)

    async def _fetch_rag_for_query(q: str) -> str:
        agent = create_agent(model=_llm, tools=[rag_tool])
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=q)]},
            config={"recursion_limit": 4},
        )
        return result["messages"][-1].content

    # Run all expanded queries in parallel
    try:
        raw_results = await asyncio.gather(
            *[_fetch_rag_for_query(q) for q in expanded_queries],
            return_exceptions=True,
        )
        result_texts = [r for r in raw_results if isinstance(r, str)]
        rag_results = _rrf_merge(result_texts) if result_texts else ""
    except Exception as exc:
        logger.error("[KnowledgeTeam] Multi-query RAG failed: %s", exc)
        rag_results = ""

    # Step 3: CRAG relevance grading
    yield {"type": "status", "message": "Thinking..."}
    is_sufficient = await evaluate_doc_context(standalone_query, rag_results)

    web_results = ""
    if not is_sufficient:
        yield {"type": "status", "message": "Searching web for supplementary context..."}

        async def _fetch_web() -> str:
            agent = create_agent(model=_llm, tools=[openai_web_search])
            from datetime import datetime
            date_str = datetime.now().strftime("%A, %B %d, %Y")
            sys_msg = SystemMessage(content=f"CURRENT DATE: {date_str}. Use this as reference for 'today' or 'latest'.")
            result = await agent.ainvoke(
                {"messages": [sys_msg, HumanMessage(content=f"Search for: {standalone_query}")]},
                config={"recursion_limit": 4},
            )
            return result["messages"][-1].content

        try:
            web_results = await _fetch_web()
        except Exception as exc:
            logger.warning("[KnowledgeTeam] Web fallback failed: %s", exc)
            web_results = ""

    # Expose raw context to hybrid synthesizer if requested
    if collect_context:
        yield {"type": "context", "rag_results": rag_results, "web_results": web_results}
        return

    # Step 4: Grounded synthesis with live token streaming
    yield {"type": "status", "message": "Generating answer..."}

    human_content = SYNTHESIZER_HUMAN.format(
        query=query,
        rag_results=rag_results,
        web_results=web_results or "None required (internal document context was complete).",
    )
    messages = [SystemMessage(content=SYNTHESIZER_SYSTEM), HumanMessage(content=human_content)]

    async for chunk in _llm.astream(messages):
        content = chunk.content
        if isinstance(content, str) and content:
            yield {"type": "token", "content": content}
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                    yield {"type": "token", "content": block["text"]}

