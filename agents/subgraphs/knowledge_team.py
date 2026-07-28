"""
agents/subgraphs/knowledge_team.py

Department A — External Knowledge Team

Improvements over v1:
  1. PARALLEL execution: RAG and Web search run at the same time (asyncio.gather),
     cutting latency by ~50% compared to the old sequential flow.
  2. QUALITY GATE: A lightweight critic checks the synthesizer's answer.
     If the score is below threshold, the synthesizer retries once with feedback.

Flow:
  [RAG Agent + Web Expert] (parallel) ──→ [Synthesizer] ──→ [Critic]
                                                               │── pass → END
                                                               └── fail → [Synthesizer retry] → END

Private state never leaks to the parent CEO graph.
"""
import asyncio
from typing import TypedDict
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent

from agents.tools import tavily_tool
from prompts.knowledge_prompts import SYNTHESIZER_SYSTEM, SYNTHESIZER_HUMAN, CRITIC_SYSTEM


# --- Private state (isolated from parent) ------------------------------

class KnowledgeState(TypedDict):
    query: str
    history_summary: str
    user_id: str            # used to filter Qdrant
    conversation_id: str    # used to filter Qdrant to only THIS conversation's documents
    rag_results: str
    web_results: str
    final_answer: str
    critic_feedback: str
    retry_count: int


# --- LLM ---------------------------------------------------------------

_llm = ChatOpenAI(model="gpt-5.4-mini-2026-03-17", temperature=0)


# --- Structured critic output ------------------------------------------

class CriticScore(BaseModel):
    passed: bool            # True if answer is good enough to return
    feedback: str           # If not passed: specific issue for the synthesizer to fix


_critic_llm = _llm.with_structured_output(CriticScore)


# --- Node: Parallel fetch (RAG + Web at the same time) ----------------

def parallel_fetch_node(state: KnowledgeState) -> dict:
    """
    Run RAG and web search concurrently.
    The RAG retriever is scoped to the current user's documents via user_id filter.
    """
    from agents.tools import build_hybrid_retriever

    # Build retriever scoped to this conversation — each call gets a fresh filtered retriever
    rag_tool = build_hybrid_retriever(user_id=state["user_id"], conversation_id=state["conversation_id"])

    search_query = state["query"]
    if state.get("history_summary"):
        search_query = f"Context: {state['history_summary']}\nQuestion: {state['query']}"

    async def _run_rag() -> str:
        agent = create_react_agent(_llm, [rag_tool])
        result = await agent.ainvoke({"messages": [HumanMessage(content=search_query)]}, config={"recursion_limit": 4})
        return result["messages"][-1].content

    async def _run_web() -> str:
        agent = create_react_agent(_llm, [tavily_tool])
        prompt = f"Search for the latest information about: {search_query}"
        result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]}, config={"recursion_limit": 4})
        return result["messages"][-1].content

    async def _gather() -> tuple[str, str]:
        return await asyncio.gather(_run_rag(), _run_web())

    loop = asyncio.new_event_loop()
    try:
        rag_results, web_results = loop.run_until_complete(_gather())
    finally:
        loop.close()
    return {"rag_results": rag_results, "web_results": web_results}


# --- Node: Synthesizer -------------------------------------------------

def synthesizer_node(state: KnowledgeState) -> dict:
    """Merge RAG + web results into one clean answer. Uses critic feedback on retry."""
    system = SYNTHESIZER_SYSTEM
    human_content = SYNTHESIZER_HUMAN.format(
        query=state["query"],
        rag_results=state["rag_results"],
        web_results=state["web_results"],
    )

    # On retry: append the critic's feedback so the LLM knows what to fix
    if state.get("critic_feedback"):
        human_content += f"\n\nIMPORTANT — Previous answer was rejected. Issue to fix: {state['critic_feedback']}"

    messages = [SystemMessage(content=system), HumanMessage(content=human_content)]
    response = _llm.invoke(messages)
    return {"final_answer": response.content}


# --- Node: Critic (Quality Gate) --------------------------------------

def critic_node(state: KnowledgeState) -> dict:
    """
    Score the synthesizer's answer.
    Returns critic_feedback="" if good, or a specific feedback string to trigger a retry.
    """
    messages = [
        SystemMessage(content=CRITIC_SYSTEM),
        HumanMessage(content=(
            f"Question: {state['query']}\n\n"
            f"Answer to evaluate:\n{state['final_answer']}"
        )),
    ]
    score: CriticScore = _critic_llm.invoke(messages)

    if score.passed:
        return {"critic_feedback": ""}          # Clears feedback → graph ends
    return {
        "critic_feedback": score.feedback, 
        "retry_count": state.get("retry_count", 0) + 1
    }


# --- Routing: should we retry or are we done? -------------------------

def _after_critic(state: KnowledgeState) -> str:
    """Route to retry synthesizer once if critic failed, otherwise end."""
    if state["critic_feedback"] and state.get("retry_count", 0) <= 1:
        return "retry"
    return "done"


# --- Build subgraph ----------------------------------------------------

def _build_knowledge_graph():
    builder = StateGraph(KnowledgeState)

    builder.add_node("parallel_fetch", parallel_fetch_node)
    builder.add_node("synthesizer", synthesizer_node)
    builder.add_node("critic", critic_node)

    builder.add_edge(START, "parallel_fetch")
    builder.add_edge("parallel_fetch", "synthesizer")
    builder.add_edge("synthesizer", "critic")
    builder.add_conditional_edges(
        "critic",
        _after_critic,
        {
            "retry": "synthesizer",   # One retry with feedback
            "done": END,
        },
    )

    return builder.compile()


knowledge_graph = _build_knowledge_graph()


# --- Enterprise RAG Helpers ----------------------------------------------

def rewrite_query(query: str, history_summary: str = "") -> str:
    """Rewrite raw user query into an explicit, standalone vector search query."""
    if not history_summary:
        return query

    from prompts.knowledge_prompts import QUERY_REWRITER_SYSTEM
    prompt = f"Chat History:\n{history_summary}\n\nLatest User Query: {query}"
    try:
        response = _llm.invoke([
            SystemMessage(content=QUERY_REWRITER_SYSTEM),
            HumanMessage(content=prompt)
        ])
        rewritten = response.content.strip()
        return rewritten if rewritten else query
    except Exception:
        return query


class EvaluationResult(BaseModel):
    sufficient: bool
    reason: str


_evaluator_llm = _llm.with_structured_output(EvaluationResult)


def evaluate_doc_context(query: str, rag_results: str) -> bool:
    """Determine if retrieved document context is sufficient to answer the query."""
    if not rag_results or len(rag_results.strip()) < 20:
        return False

    from prompts.knowledge_prompts import EVALUATOR_SYSTEM
    try:
        res = _evaluator_llm.invoke([
            SystemMessage(content=EVALUATOR_SYSTEM),
            HumanMessage(content=f"Query: {query}\n\nRetrieved Document Context:\n{rag_results}")
        ])
        return res.sufficient
    except Exception:
        return True


def _format_history(history: list) -> str:
    """Format history list safely whether elements are dicts or BaseMessage objects."""
    if not history:
        return ""
    formatted = []
    for m in history[-4:]:
        if isinstance(m, dict):
            role = m.get("role", "user").upper()
            content = m.get("content", "")
        else:
            role = getattr(m, "type", "human").upper()
            content = getattr(m, "content", "")
        if content:
            formatted.append(f"{role}: {content}")
    return "\n".join(formatted)


# --- Wrapper (called by parent graph) ----------------------------------

def run_knowledge_team(query: str, user_id: str, conversation_id: str, history: list = None) -> str:
    """Entry point for synchronous graph invocation."""
    history_summary = _format_history(history)

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


async def astream_knowledge_team(query: str, user_id: str, conversation_id: str, history: list = None):
    """
    Enterprise RAG Async generator yielding progress events and streaming synthesizer tokens in real-time.
    Yields dicts with:
      {"type": "status", "message": "..."} OR {"type": "token", "content": "..."}
    """
    history_summary = _format_history(history)

    # Step 1: Conversational Query Rewriting
    yield {"type": "status", "message": "Analyzing query..."}
    standalone_query = await asyncio.to_thread(rewrite_query, query, history_summary)

    # Initialize KnowledgeState object
    state: KnowledgeState = {
        "query": standalone_query,
        "history_summary": history_summary,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "rag_results": "",
        "web_results": "",
        "final_answer": "",
        "critic_feedback": "",
        "retry_count": 0,
    }

    # Step 2: Document Vector Retrieval (Qdrant)
    yield {"type": "status", "message": "Searching documents..."}
    from agents.tools import build_hybrid_retriever
    rag_tool = build_hybrid_retriever(user_id=user_id, conversation_id=conversation_id)

    async def _fetch_rag() -> str:
        agent = create_react_agent(_llm, [rag_tool])
        result = await agent.ainvoke({"messages": [HumanMessage(content=standalone_query)]}, config={"recursion_limit": 4})
        return result["messages"][-1].content

    try:
        state["rag_results"] = await _fetch_rag()
    except Exception as e:
        state["rag_results"] = f"Document retrieval error: {str(e)}"

    # Step 3: Adaptive Web Search Gating
    yield {"type": "status", "message": "Thinking..."}
    is_sufficient = await asyncio.to_thread(evaluate_doc_context, standalone_query, state["rag_results"])

    if not is_sufficient:
        yield {"type": "status", "message": "Searching web..."}
        async def _fetch_web() -> str:
            agent = create_react_agent(_llm, [tavily_tool])
            from datetime import datetime
            current_time = datetime.now().strftime("%A, %B %d, %Y")
            sys_msg = SystemMessage(content=f"CURRENT SYSTEM DATE: {current_time}. IMPORTANT: Always use this date as your reference for 'today', 'latest news', or current events.")
            prompt = f"Search for: {standalone_query}"
            res = await agent.ainvoke({"messages": [sys_msg, HumanMessage(content=prompt)]}, config={"recursion_limit": 4})
            return res["messages"][-1].content
        try:
            state["web_results"] = await _fetch_web()
        except Exception:
            state["web_results"] = ""

    # Step 4: Grounded Synthesis & Live Token Streaming
    yield {"type": "status", "message": "Thinking..."}

    system = SYNTHESIZER_SYSTEM
    human_content = SYNTHESIZER_HUMAN.format(
        query=query,
        rag_results=state["rag_results"],
        web_results=state["web_results"] if state["web_results"] else "None required (Internal document context was complete).",
    )
    messages = [SystemMessage(content=system), HumanMessage(content=human_content)]

    async for chunk in _llm.astream(messages):
        content = chunk.content
        if isinstance(content, str) and content:
            yield {"type": "token", "content": content}
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                    yield {"type": "token", "content": block["text"]}



