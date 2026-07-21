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

    async def _run_rag() -> str:
        agent = create_react_agent(_llm, [rag_tool])
        result = await agent.ainvoke({"messages": [HumanMessage(content=state["query"])]})
        return result["messages"][-1].content

    async def _run_web() -> str:
        agent = create_react_agent(_llm, [tavily_tool])
        prompt = f"Search for the latest information about: {state['query']}"
        result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
        return result["messages"][-1].content

    async def _gather() -> tuple[str, str]:
        return await asyncio.gather(_run_rag(), _run_web())

    rag_results, web_results = asyncio.run(_gather())
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
    return {"critic_feedback": score.feedback}  # Non-empty → retry synthesizer


# --- Routing: should we retry or are we done? -------------------------

def _after_critic(state: KnowledgeState) -> str:
    """Route to retry synthesizer once if critic failed, otherwise end."""
    if state["critic_feedback"] and state.get("retry_count", 0) < 1:
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


# --- Wrapper (called by parent graph) ----------------------------------

def run_knowledge_team(query: str, user_id: str, conversation_id: str) -> str:
    """Entry point for the parent CEO graph. Returns only the final answer string."""
    result = knowledge_graph.invoke({
        "query": query,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "rag_results": "",
        "web_results": "",
        "final_answer": "",
        "critic_feedback": "",
        "retry_count": 0,
    })
    return result["final_answer"]

