"""
app/agents/teams/knowledge.py

Enterprise Document RAG & CRAG Specialist Department.
Built as a compiled LangGraph CRAG subgraph:
  [START] -> [rewrite] -> [retrieve] -> [evaluate] -> (sufficient?)
                                            │
                   ┌────────────────────────┴────────────────────────┐
                   │ is_sufficient=True                              │ is_sufficient=False
                   ▼                                                 ▼
             [synthesize]                                     [web_fallback]
                   │                                                 │
                   ▼                                                 ▼
                 [END] ◄─────────────────────────────────────── [synthesize]

Performance note:
  RAG retrieval is a direct Python call to rag_tool.func() in a thread pool (Qdrant
  via langchain-qdrant). Zero LLM agent overhead during retrieval.
"""
import asyncio
import logging
import re
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langsmith import traceable
from pydantic import BaseModel

from app.agents.context import format_history
from app.agents.prompts.knowledge import (
    EVALUATOR_SYSTEM,
    QUERY_REWRITER_SYSTEM,
    SYNTHESIZER_HUMAN,
    SYNTHESIZER_SYSTEM,
)
from app.agents.tools import build_hybrid_retriever, web_search_tool
from app.config import DEFAULT_MODEL, FAST_MODEL

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
# Subgraph State Definition
# ---------------------------------------------------------------------------

class KnowledgeTeamState(TypedDict):
    query: str
    user_id: str
    conversation_id: str
    history_summary: str
    rewritten_query: str
    expanded_queries: list[str]
    rag_results: str
    is_sufficient: bool
    web_results: str
    final_answer: str
    collect_context: bool


# ---------------------------------------------------------------------------
# CRAG Helper Utilities & Nodes
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
        rewritten = response.content.strip() if isinstance(response.content, str) else str(response.content).strip()
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
        if isinstance(result, EvaluationResult):
            return result.sufficient
        if isinstance(result, dict):
            return bool(result.get("sufficient", True))
        return bool(getattr(result, "sufficient", True))
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
        text = response.content.strip() if isinstance(response.content, str) else str(response.content).strip()
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
# LangGraph Subgraph Nodes
# ---------------------------------------------------------------------------

@traceable(name="Knowledge Rewrite Node", run_type="chain")
async def rewrite_node(state: KnowledgeTeamState) -> dict:
    """Decontextualize query against chat history."""
    standalone = await rewrite_query(state["query"], state.get("history_summary", ""))
    return {"rewritten_query": standalone}


@traceable(name="Knowledge Retrieve Node", run_type="chain")
async def retrieve_node(state: KnowledgeTeamState) -> dict:
    """Expand query and fetch Qdrant vector chunks concurrently via thread pool."""
    standalone_query = state.get("rewritten_query") or state["query"]
    expanded_queries = await _expand_queries(standalone_query)
    logger.info("[KnowledgeTeam] Expanded to %d queries: %s", len(expanded_queries), expanded_queries)

    rag_tool = build_hybrid_retriever(
        user_id=state["user_id"],
        conversation_id=state["conversation_id"],
    )

    async def _fetch_rag_for_query(q: str) -> str:
        try:
            return await rag_tool.ainvoke(q)
        except Exception as exc:
            logger.warning("[KnowledgeTeam] RAG fetch failed for query '%s': %s", q, exc)
            return ""

    raw_results = await asyncio.gather(
        *[_fetch_rag_for_query(q) for q in expanded_queries],
        return_exceptions=True,
    )
    result_texts = [r for r in raw_results if isinstance(r, str) and r]
    rag_results = _rrf_merge(result_texts) if result_texts else ""
    return {"expanded_queries": expanded_queries, "rag_results": rag_results}


@traceable(name="Knowledge Evaluate Node", run_type="chain")
async def evaluate_node(state: KnowledgeTeamState) -> dict:
    """Grade relevance and sufficiency of retrieved document chunks."""
    standalone_query = state.get("rewritten_query") or state["query"]
    rag_results = state.get("rag_results", "")
    is_sufficient = await evaluate_doc_context(standalone_query, rag_results)
    return {"is_sufficient": is_sufficient}


@traceable(name="Knowledge Web Fallback Node", run_type="chain")
async def web_fallback_node(state: KnowledgeTeamState) -> dict:
    """Execute live web search fallback when document context is insufficient."""
    standalone_query = state.get("rewritten_query") or state["query"]
    try:
        web_results = await web_search_tool.ainvoke(standalone_query)
    except Exception as exc:
        logger.warning("[KnowledgeTeam] Web fallback failed: %s", exc)
        web_results = ""
    return {"web_results": web_results}


@traceable(name="Knowledge Synthesize Node", run_type="chain")
async def synthesize_node(state: KnowledgeTeamState) -> dict:
    """Generate grounded answer from document context and optional web context."""
    human_content = SYNTHESIZER_HUMAN.format(
        query=state["query"],
        rag_results=state.get("rag_results", ""),
        web_results=state.get("web_results") or "None required (internal document context was complete).",
    )
    messages = [SystemMessage(content=SYNTHESIZER_SYSTEM), HumanMessage(content=human_content)]
    response = await _llm.ainvoke(messages)
    content = response.content if isinstance(response.content, str) else str(response.content)
    return {"final_answer": content}


def _route_evaluation(state: KnowledgeTeamState) -> str:
    """Route to web fallback if document context is insufficient, otherwise synthesize or finish."""
    if not state.get("is_sufficient", True):
        return "web_fallback"
    if state.get("collect_context", False):
        return END
    return "synthesize"


def _route_after_web_fallback(state: KnowledgeTeamState) -> str:
    """After web fallback, finish if only collecting context, otherwise synthesize."""
    if state.get("collect_context", False):
        return END
    return "synthesize"


# ---------------------------------------------------------------------------
# Graph Assembly & Compilation
# ---------------------------------------------------------------------------

def _build_knowledge_graph():
    """Compile the Knowledge Team CRAG subgraph."""
    builder = StateGraph(KnowledgeTeamState)

    builder.add_node("rewrite", rewrite_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("web_fallback", web_fallback_node)
    builder.add_node("synthesize", synthesize_node)

    builder.add_edge(START, "rewrite")
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("retrieve", "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        _route_evaluation,
        {
            "synthesize": "synthesize",
            "web_fallback": "web_fallback",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "web_fallback",
        _route_after_web_fallback,
        {
            "synthesize": "synthesize",
            END: END,
        },
    )
    builder.add_edge("synthesize", END)

    return builder.compile()


_knowledge_graph = _build_knowledge_graph()


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
    Streams from the compiled LangGraph CRAG subgraph.
    """
    history_summary = format_history(history) if history else ""

    initial_state: KnowledgeTeamState = {
        "query": query,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "history_summary": history_summary,
        "rewritten_query": "",
        "expanded_queries": [],
        "rag_results": "",
        "is_sufficient": True,
        "web_results": "",
        "final_answer": "",
        "collect_context": collect_context,
    }

    yield {"type": "status", "message": "Analyzing query..."}

    synthesizing_started = False
    tokens_streamed = False
    rag_results = ""
    web_results = ""

    async for mode, payload in _knowledge_graph.astream(
        initial_state,
        stream_mode=["messages", "updates"],
    ):
        if mode == "updates":
            for node_name, update in payload.items():
                if node_name == "rewrite":
                    yield {"type": "status", "message": "Searching documents..."}
                elif node_name == "retrieve":
                    rag_results = update.get("rag_results", "")
                    yield {"type": "status", "message": "Thinking..."}
                elif node_name == "evaluate":
                    if not update.get("is_sufficient", True):
                        yield {"type": "status", "message": "Searching web for supplementary context..."}
                elif node_name == "web_fallback":
                    web_results = update.get("web_results", "")
                elif node_name == "synthesize":
                    final_answer = update.get("final_answer", "")
                    if not tokens_streamed and final_answer:
                        if not synthesizing_started:
                            yield {"type": "status", "message": "Generating answer..."}
                        yield {"type": "token", "content": final_answer}

        elif mode == "messages":
            chunk, metadata = payload
            if metadata.get("langgraph_node") == "synthesize":
                if not synthesizing_started:
                    synthesizing_started = True
                    yield {"type": "status", "message": "Generating answer..."}

                content = chunk.content
                if isinstance(content, str) and content:
                    tokens_streamed = True
                    yield {"type": "token", "content": content}
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                            tokens_streamed = True
                            yield {"type": "token", "content": block["text"]}

    if collect_context:
        yield {"type": "context", "rag_results": rag_results, "web_results": web_results}
