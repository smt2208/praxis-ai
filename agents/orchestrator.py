"""
agents/orchestrator.py

The CEO — main stateless LangGraph orchestrator.
Reads injected chat history, routes to the right department,
and returns the final answer.  No checkpointer — fully stateless.

Routing logic lives in agents/routing.py.
"""
import logging
from typing import TypedDict, Literal, Annotated

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langsmith import traceable

from app.config import DEFAULT_MODEL
from agents.utils import format_history, build_doc_context, build_user_profile_context
from agents.routing import resolve_route
from agents.subgraphs.knowledge_team import run_knowledge_team
from agents.subgraphs.research_team import run_research_team
from agents.subgraphs.general_agent import run_general_agent
from prompts.orchestrator_prompts import FOLLOW_UP_SYSTEM
from app.services.memory import retrieve_memories

logger = logging.getLogger(__name__)

_followup_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.7)


# ---------------------------------------------------------------------------
# Orchestrator state
# ---------------------------------------------------------------------------

class OrchestratorState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    query: str
    user_id: str
    conversation_id: str
    has_documents: bool
    route: str
    final_answer: str
    memory_context: str


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def ceo_node(state: OrchestratorState) -> dict:
    """Analyze the conversation and route to the correct department."""
    history_text = format_history(state["messages"][:-1], last_n=20)
    doc_context = build_doc_context(state["has_documents"])
    route = resolve_route(state["query"], history_text, doc_context, state["has_documents"])
    return {"route": route}


def knowledge_team_node(state: OrchestratorState) -> dict:
    """Delegates to Knowledge Team with user_id and conversation_id for document isolation."""
    answer = run_knowledge_team(
        state["query"],
        history=state["messages"][:-1],
        user_id=state["user_id"],
        conversation_id=state["conversation_id"],
    )
    return {"final_answer": answer}


def research_team_node(state: OrchestratorState) -> dict:
    logger.info("[Research Team] Executing for query: '%s'", state["query"][:60])
    answer = run_research_team(state["query"], history=state["messages"][:-1])
    return {"final_answer": answer}


def general_agent_node(state: OrchestratorState) -> dict:
    """Handles everyday questions with web search — ChatGPT-like experience."""
    answer = run_general_agent(state["query"], state["messages"][:-1])
    return {"final_answer": answer}


def follow_up_node(state: OrchestratorState) -> dict:
    """Handles conversational replies, rephrasing, or summaries using history."""
    recent_msgs = list(state["messages"][-10:])
    messages = [SystemMessage(content=FOLLOW_UP_SYSTEM)] + recent_msgs
    response = _followup_llm.invoke(messages)
    return {"final_answer": response.content}


def route_to_department(state: OrchestratorState) -> str:
    return state["route"]


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def _build_main_graph():
    builder = StateGraph(OrchestratorState)

    builder.add_node("ceo", ceo_node)
    builder.add_node("knowledge_team_node", knowledge_team_node)
    builder.add_node("research_team_node", research_team_node)
    builder.add_node("general_agent_node", general_agent_node)
    builder.add_node("follow_up_node", follow_up_node)

    builder.add_edge(START, "ceo")
    builder.add_conditional_edges(
        "ceo",
        route_to_department,
        {
            "knowledge_team": "knowledge_team_node",
            "research_team":  "research_team_node",
            "general":        "general_agent_node",
            "follow_up":      "follow_up_node",
        },
    )
    builder.add_edge("knowledge_team_node", END)
    builder.add_edge("research_team_node", END)
    builder.add_edge("general_agent_node", END)
    builder.add_edge("follow_up_node", END)

    return builder.compile()


main_graph = _build_main_graph()


# ---------------------------------------------------------------------------
# History conversion helper
# ---------------------------------------------------------------------------

def _history_to_messages(history: list[dict]) -> list[BaseMessage]:
    """Convert list of {"role": ..., "content": ...} dicts to LangChain BaseMessage objects."""
    result = []
    for msg in history:
        if msg["role"] == "user":
            result.append(HumanMessage(content=msg["content"]))
        else:
            result.append(AIMessage(content=msg["content"]))
    return result


# ---------------------------------------------------------------------------
# Public entry points (called by FastAPI routers)
# ---------------------------------------------------------------------------

@traceable(name="Orchestrator Graph Run", run_type="chain")
def invoke_graph(
    query: str,
    history: list[dict],
    user_id: str,
    conversation_id: str,
    has_documents: bool,
    memory_enabled: bool = True,
    user_profile: dict | None = None,
) -> dict:
    """Synchronous invocation. Returns {"answer": str, "route": str}."""
    messages = _history_to_messages(history)
    messages.append(HumanMessage(content=query))

    # Retrieve long-term memories and profile for this user
    memory_context = retrieve_memories(user_id, query) if memory_enabled else ""
    profile_context = build_user_profile_context(user_profile)

    combined_context = "\n\n".join(filter(None, [profile_context, memory_context]))
    if combined_context:
        messages.insert(0, SystemMessage(content=combined_context))

    result = main_graph.invoke({
        "messages": messages,
        "query": query,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "has_documents": has_documents,
        "route": "",
        "final_answer": "",
        "memory_context": memory_context,
    })
    return {"answer": result["final_answer"], "route": result["route"]}


@traceable(name="Orchestrator SSE Stream", run_type="chain")
async def astream_graph_events(
    query: str,
    history: list[dict],
    user_id: str,
    conversation_id: str,
    has_documents: bool,
    user_tz: str = None,
    memory_enabled: bool = True,
    user_profile: dict | None = None,
):
    """
    Async generator for SSE streaming.
    Yields dicts: {"event": str, "data": dict}
    """
    import asyncio
    from agents.subgraphs.general_agent import astream_general_agent
    from agents.subgraphs.knowledge_team import astream_knowledge_team
    from agents.subgraphs.research_team import astream_research_team

    messages = _history_to_messages(history)

    # Retrieve long-term memories and profile for this user
    memory_context = (await asyncio.to_thread(retrieve_memories, user_id, query)) if memory_enabled else ""
    profile_context = build_user_profile_context(user_profile)

    combined_context = "\n\n".join(filter(None, [profile_context, memory_context]))
    if combined_context:
        messages.insert(0, SystemMessage(content=combined_context))

    # ── Step 1: Route ──────────────────────────────────────────────────
    yield {"event": "agent_start", "data": {"agent": "ceo", "message": "Thinking..."}}

    doc_context = build_doc_context(has_documents)
    history_text = format_history(messages, last_n=20)
    route = await asyncio.to_thread(resolve_route, query, history_text, doc_context, has_documents)

    _status = {
        "knowledge_team": "Searching documents...",
        "research_team":  "Researching...",
        "general":        "Thinking...",
    }
    yield {"event": "agent_start", "data": {"agent": route, "message": _status.get(route, "Thinking...")}}

    # ── Step 2: Execute department ──────────────────────────────────────
    if route == "general":
        async for token in astream_general_agent(query, messages, user_tz=user_tz):
            yield {"event": "token", "data": {"agent": "general", "content": token}}

    elif route == "follow_up":
        recent_msgs = messages[-10:] if len(messages) > 10 else messages
        followup_messages = [SystemMessage(content=FOLLOW_UP_SYSTEM)] + recent_msgs + [HumanMessage(content=query)]
        async for chunk in _followup_llm.astream(followup_messages):
            content = chunk.content
            if isinstance(content, str) and content:
                yield {"event": "token", "data": {"agent": "follow_up", "content": content}}
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                        yield {"event": "token", "data": {"agent": "follow_up", "content": block["text"]}}

    elif route == "knowledge_team":
        async for evt in astream_knowledge_team(query, user_id=user_id, conversation_id=conversation_id, history=messages):
            if evt["type"] == "status":
                yield {"event": "agent_start", "data": {"agent": "knowledge_team", "message": evt["message"]}}
            elif evt["type"] == "token":
                yield {"event": "token", "data": {"agent": "knowledge_team", "content": evt["content"]}}

    elif route == "research_team":
        async for evt in astream_research_team(query, history=messages):
            if evt["type"] == "status":
                yield {"event": "agent_start", "data": {"agent": "research_team", "message": evt["message"]}}
            elif evt["type"] == "token":
                yield {"event": "token", "data": {"agent": "research_team", "content": evt["content"]}}

    yield {"event": "done", "data": {"route": route}}
