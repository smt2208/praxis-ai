"""
agents/subgraphs/knowledge_team.py

Public entry points for the Knowledge Team department.
Heavy implementation is split across:
  - knowledge_graph.py  → LangGraph state + nodes + compiled graph
  - knowledge_rag.py    → query rewriting + doc-context evaluation helpers

This file contains:
  run_knowledge_team      — synchronous wrapper (called by LangGraph CEO node)
  astream_knowledge_team  — async streaming generator (called by SSE endpoint)

CRAG Enhancements:
  - Multi-query expansion: generates 2 complementary search queries per user message.
  - Relevance grading: grades retrieved chunks (sufficient / partial / none).
    - Sufficient → direct synthesis.
    - Partial/None → triggers OpenAI web search fallback, merged with document context.
"""
import asyncio
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from app.config import DEFAULT_MODEL, FAST_MODEL
from agents.utils import format_history
from agents.tools import openai_web_search
from agents.subgraphs.knowledge_graph import knowledge_graph, KnowledgeState
from agents.subgraphs.knowledge_rag import rewrite_query, evaluate_doc_context
from prompts.knowledge_prompts import SYNTHESIZER_SYSTEM, SYNTHESIZER_HUMAN

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)
_fast_llm = ChatOpenAI(model=FAST_MODEL, temperature=0)


# ---------------------------------------------------------------------------
# CRAG: Multi-query expander
# ---------------------------------------------------------------------------

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
        # Safe parse — extract strings between quotes
        import re
        found = re.findall(r'"([^"]+)"', text)
        queries = [q.strip() for q in found if q.strip()]
        if len(queries) >= 2:
            return [query] + queries[:2]   # original + 2 variants
    except Exception as exc:
        logger.debug("[KnowledgeTeam] Query expansion failed (using original): %s", exc)
    return [query]


# ---------------------------------------------------------------------------
# CRAG: Reciprocal Rank Fusion deduplication
# ---------------------------------------------------------------------------

def _rrf_merge(result_sets: list[str]) -> str:
    """
    Merge multiple retrieval result strings into one deduplicated context.
    Simple implementation: concatenate and deduplicate by paragraph/chunk boundary.
    """
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
# Synchronous wrapper — called by the CEO LangGraph node
# ---------------------------------------------------------------------------

@traceable(name="Knowledge Team Run", run_type="chain")
def run_knowledge_team(query: str, user_id: str, conversation_id: str, history: list = None) -> str:
    """Entry point for synchronous graph invocation from the CEO node."""
    history_summary = format_history(history)
    standalone_query = rewrite_query(query, history_summary)

    result = knowledge_graph.invoke({
        "query": standalone_query,
        "history_summary": history_summary,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "rag_results": "",
        "web_results": "",
        "final_answer": "",
        "critic_feedback": "",
        "retry_count": 0,
    })
    return result["final_answer"]


# ---------------------------------------------------------------------------
# Async streaming generator — called by the SSE chat endpoint
# ---------------------------------------------------------------------------

@traceable(name="Knowledge Team Stream", run_type="chain")
async def astream_knowledge_team(
    query: str,
    user_id: str,
    conversation_id: str,
    history: list = None,
    collect_context: bool = False,
):
    """
    Enterprise RAG streaming with CRAG: yields progress events then synthesizer tokens.

    Yields dicts:
        {"type": "status", "message": "..."}
        {"type": "token",  "content": "..."}

    If collect_context=True, also yields a final event:
        {"type": "context", "rag_results": str, "web_results": str}
    This is used by the hybrid synthesizer to access raw research output.
    """
    from langchain.agents import create_agent
    from agents.tools import build_hybrid_retriever

    history_summary = format_history(history)

    # Step 1: Query rewriting
    yield {"type": "status", "message": "Analyzing query..."}
    standalone_query = await asyncio.to_thread(rewrite_query, query, history_summary)

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
    is_sufficient = await asyncio.to_thread(evaluate_doc_context, standalone_query, rag_results)

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
