"""
agents/subgraphs/knowledge_graph.py

LangGraph state + node definitions for the Knowledge Team subgraph.
Extracted from knowledge_team.py so the graph definition is separate
from the RAG utilities and the streaming wrapper.

Exports:
    KnowledgeState   — private TypedDict for this subgraph
    knowledge_graph  — compiled LangGraph graph
"""
import asyncio
import logging
from typing import TypedDict

from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langchain.agents import create_agent

from app.config import DEFAULT_MODEL
from agents.tools import tavily_tool
from prompts.knowledge_prompts import SYNTHESIZER_SYSTEM, SYNTHESIZER_HUMAN, CRITIC_SYSTEM

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


# ---------------------------------------------------------------------------
# Private state — never leaks to the parent CEO graph
# ---------------------------------------------------------------------------

class KnowledgeState(TypedDict):
    query: str
    history_summary: str
    user_id: str           # used to filter Qdrant
    conversation_id: str   # scopes retrieval to THIS conversation's documents
    rag_results: str
    web_results: str
    final_answer: str
    critic_feedback: str
    retry_count: int


# ---------------------------------------------------------------------------
# Critic structured output
# ---------------------------------------------------------------------------

class CriticScore(BaseModel):
    passed: bool    # True → answer is good enough to return
    feedback: str   # If not passed: specific issue for the synthesizer to fix


_critic_llm = _llm.with_structured_output(CriticScore)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def parallel_fetch_node(state: KnowledgeState) -> dict:
    """
    Run RAG and web search concurrently.
    The RAG retriever is scoped to the current user's conversation via user_id + conversation_id.
    """
    from agents.tools import build_hybrid_retriever

    rag_tool = build_hybrid_retriever(user_id=state["user_id"], conversation_id=state["conversation_id"])

    search_query = state["query"]
    if state.get("history_summary"):
        search_query = f"Context: {state['history_summary']}\nQuestion: {state['query']}"

    async def _run_rag() -> str:
        agent = create_agent(model=_llm, tools=[rag_tool])
        result = await agent.ainvoke({"messages": [HumanMessage(content=search_query)]}, config={"recursion_limit": 4})
        return result["messages"][-1].content

    async def _run_web() -> str:
        agent = create_agent(model=_llm, tools=[tavily_tool])
        prompt = f"Search for the latest information about: {search_query}"
        result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]}, config={"recursion_limit": 4})
        return result["messages"][-1].content

    async def _gather() -> tuple[str, str]:
        return await asyncio.gather(_run_rag(), _run_web())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        rag_results, web_results = loop.run_until_complete(_gather())
    finally:
        loop.close()
        asyncio.set_event_loop(None)

    return {"rag_results": rag_results, "web_results": web_results}


def synthesizer_node(state: KnowledgeState) -> dict:
    """Merge RAG + web results into one clean answer. Uses critic feedback on retry."""
    human_content = SYNTHESIZER_HUMAN.format(
        query=state["query"],
        rag_results=state["rag_results"],
        web_results=state["web_results"],
    )
    if state.get("critic_feedback"):
        human_content += f"\n\nIMPORTANT — Previous answer was rejected. Issue to fix: {state['critic_feedback']}"

    messages = [SystemMessage(content=SYNTHESIZER_SYSTEM), HumanMessage(content=human_content)]
    response = _llm.invoke(messages)
    return {"final_answer": response.content}


def critic_node(state: KnowledgeState) -> dict:
    """
    Score the synthesizer's answer.
    Returns critic_feedback='' if good, or a specific feedback string to trigger a retry.
    """
    messages = [
        SystemMessage(content=CRITIC_SYSTEM),
        HumanMessage(content=f"Question: {state['query']}\n\nAnswer to evaluate:\n{state['final_answer']}"),
    ]
    score: CriticScore = _critic_llm.invoke(messages)
    if score.passed:
        return {"critic_feedback": ""}
    return {"critic_feedback": score.feedback, "retry_count": state.get("retry_count", 0) + 1}


def _after_critic(state: KnowledgeState) -> str:
    """Route to retry synthesizer once if critic failed, otherwise end."""
    if state["critic_feedback"] and state.get("retry_count", 0) <= 1:
        return "retry"
    return "done"


# ---------------------------------------------------------------------------
# Graph compilation
# ---------------------------------------------------------------------------

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
        {"retry": "synthesizer", "done": END},
    )
    return builder.compile()


knowledge_graph = _build_knowledge_graph()
