"""
agents/orchestrator.py

The CEO — main stateless LangGraph orchestrator.
Reads injected chat history, routes to the right department,
and returns the final answer. No checkpointer — fully stateless.
"""
import logging
from typing import TypedDict, Literal, Annotated

from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langsmith import traceable

from app.config import DEFAULT_MODEL
from agents.utils import format_history, build_doc_context
from agents.subgraphs.knowledge_team import run_knowledge_team
from agents.subgraphs.research_team import run_research_team
from agents.subgraphs.general_agent import run_general_agent
from prompts.orchestrator_prompts import ROUTER_SYSTEM, FOLLOW_UP_SYSTEM

logger = logging.getLogger(__name__)


# --- Orchestrator state (shared across all top-level nodes) ------------

class OrchestratorState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    query: str
    user_id: str
    conversation_id: str
    has_documents: bool
    route: str
    final_answer: str


# --- Structured routing output -----------------------------------------

class RouteDecision(BaseModel):
    """The CEO must output exactly this schema — no free-form text."""
    route: Literal["knowledge_team", "research_team", "follow_up", "general"]


# --- LLMs --------------------------------------------------------------

_ceo_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)
_followup_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.7)
_router_llm = _ceo_llm.with_structured_output(RouteDecision)


# --- Node: CEO (Router) ------------------------------------------------

def ceo_node(state: OrchestratorState) -> dict:
    """Analyze the conversation and route to the correct department."""
    history_text = format_history(state["messages"][:-1], last_n=10)
    doc_context = build_doc_context(state["has_documents"])

    routing_messages = [
        SystemMessage(content=ROUTER_SYSTEM),
        HumanMessage(content=(
            f"{doc_context}\n\nConversation so far:\n{history_text}\n\nLatest user message: {state['query']}"
            if history_text else
            f"{doc_context}\n\nUser message: {state['query']}"
        )),
    ]
    decision: RouteDecision = _router_llm.invoke(routing_messages)
    route = decision.route

    # Hard gate: if the user has never uploaded a document, knowledge_team is unreachable.
    # This cannot be bypassed by prompt injection — it's enforced in Python.
    if route == "knowledge_team" and not state["has_documents"]:
        route = "general"

    logger.info("[CEO Router] Query: '%s' -> Routed to: %s", state["query"][:60], route)
    return {"route": route}


# --- Node: Knowledge Team wrapper --------------------------------------

def knowledge_team_node(state: OrchestratorState) -> dict:
    """Delegates to Knowledge Team with user_id and conversation_id for document isolation."""
    answer = run_knowledge_team(
        state["query"],
        history=state["messages"][:-1],
        user_id=state["user_id"],
        conversation_id=state["conversation_id"],
    )
    return {"final_answer": answer}


# --- Node: Research Team wrapper ---------------------------------------

def research_team_node(state: OrchestratorState) -> dict:
    logger.info("[Deep Research Team] Executing for query: '%s'", state["query"][:60])
    answer = run_research_team(state["query"], history=state["messages"][:-1])
    return {"final_answer": answer}


# --- Node: General Agent ----------------------------------------------

def general_agent_node(state: OrchestratorState) -> dict:
    """Handles everyday questions with web search — ChatGPT-like experience."""
    answer = run_general_agent(state["query"], state["messages"][:-1])
    return {"final_answer": answer}


# --- Node: Follow-Up Agent --------------------------------------------

def follow_up_node(state: OrchestratorState) -> dict:
    """Handles conversational replies, rephrasing, or summaries using history."""
    messages = [SystemMessage(content=FOLLOW_UP_SYSTEM)] + list(state["messages"])
    response = _followup_llm.invoke(messages)
    return {"final_answer": response.content}


# --- Routing function --------------------------------------------------

def route_to_department(state: OrchestratorState) -> str:
    return state["route"]


# --- Build main graph (STATELESS — no checkpointer) -------------------

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
            "research_team": "research_team_node",
            "general": "general_agent_node",
            "follow_up": "follow_up_node",
        },
    )
    builder.add_edge("knowledge_team_node", END)
    builder.add_edge("research_team_node", END)
    builder.add_edge("general_agent_node", END)
    builder.add_edge("follow_up_node", END)

    return builder.compile()


main_graph = _build_main_graph()


# --- Helper: Convert DB history dicts to LangChain messages -----------

def _history_to_messages(history: list[dict]) -> list[BaseMessage]:
    """Convert list of {"role": ..., "content": ...} dicts to BaseMessage objects."""
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    return messages


# --- Public invoke function -------------------------------------------

@traceable(name="Orchestrator Graph Run", run_type="chain")
def invoke_graph(query: str, history: list[dict], user_id: str, conversation_id: str, has_documents: bool) -> dict:
    """
    Entry point for the FastAPI router (synchronous invocation).
    Returns {"answer": str, "route": str}
    """
    messages = _history_to_messages(history)
    messages.append(HumanMessage(content=query))

    result = main_graph.invoke({
        "messages": messages,
        "query": query,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "has_documents": has_documents,
        "route": "",
        "final_answer": "",
    })

    return {
        "answer": result["final_answer"],
        "route": result["route"],
    }


@traceable(name="Orchestrator SSE Stream", run_type="chain")
async def astream_graph_events(query: str, history: list[dict], user_id: str, conversation_id: str, has_documents: bool, user_tz: str = None):
    """
    Async generator for SSE streaming.
    Yields dicts with {"event": ..., "data": ...}
    """
    import asyncio
    from agents.subgraphs.general_agent import astream_general_agent

    messages = _history_to_messages(history)

    # Step 1: CEO Router
    yield {"event": "agent_start", "data": {"agent": "ceo", "message": "Thinking..."}}

    doc_context = build_doc_context(has_documents)
    history_text = format_history(messages, last_n=10)

    routing_messages = [
        SystemMessage(content=ROUTER_SYSTEM),
        HumanMessage(content=(
            f"{doc_context}\n\nConversation so far:\n{history_text}\n\nLatest user message: {query}"
            if history_text else f"{doc_context}\n\nUser message: {query}"
        )),
    ]
    decision: RouteDecision = await asyncio.to_thread(_router_llm.invoke, routing_messages)
    route = decision.route
    if route == "knowledge_team" and not has_documents:
        route = "general"

    status_messages = {
        "knowledge_team": "Searching documents...",
        "research_team": "Researching...",
        "general": "Searching web...",
    }
    yield {"event": "agent_start", "data": {"agent": route, "message": status_messages.get(route, "Thinking...")}}

    # Step 2: Department execution & token streaming
    if route == "general":
        async for token in astream_general_agent(query, messages, user_tz=user_tz):
            yield {"event": "token", "data": {"agent": "general", "content": token}}

    elif route == "follow_up":
        followup_messages = [SystemMessage(content=FOLLOW_UP_SYSTEM)] + messages + [HumanMessage(content=query)]
        async for chunk in _followup_llm.astream(followup_messages):
            content = chunk.content
            if isinstance(content, str) and content:
                yield {"event": "token", "data": {"agent": "follow_up", "content": content}}
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                        yield {"event": "token", "data": {"agent": "follow_up", "content": block["text"]}}

    elif route == "knowledge_team":
        from agents.subgraphs.knowledge_team import astream_knowledge_team
        async for evt in astream_knowledge_team(query, user_id=user_id, conversation_id=conversation_id, history=messages):
            if evt["type"] == "status":
                yield {"event": "agent_start", "data": {"agent": "knowledge_team", "message": evt["message"]}}
            elif evt["type"] == "token":
                yield {"event": "token", "data": {"agent": "knowledge_team", "content": evt["content"]}}

    elif route == "research_team":
        from agents.subgraphs.research_team import astream_research_team
        async for evt in astream_research_team(query, history=messages):
            if evt["type"] == "status":
                yield {"event": "agent_start", "data": {"agent": "research_team", "message": evt["message"]}}
            elif evt["type"] == "token":
                yield {"event": "token", "data": {"agent": "research_team", "content": evt["content"]}}

    yield {"event": "done", "data": {"route": route}}
