"""
agents/orchestrator.py

The CEO — main stateless LangGraph orchestrator.
Reads injected chat history, routes to the right department,
and returns the final answer. No checkpointer — fully stateless.
"""
from typing import TypedDict, Literal, Annotated
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent

from agents.subgraphs.knowledge_team import run_knowledge_team
from agents.subgraphs.research_team import run_research_team
from agents.subgraphs.general_agent import run_general_agent
from prompts.orchestrator_prompts import ROUTER_SYSTEM, FOLLOW_UP_SYSTEM


# --- Orchestrator state (shared across all top-level nodes) ------------

class OrchestratorState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    query: str
    user_id: str       # propagated from JWT — needed by knowledge_team for doc isolation
    conversation_id: str # needed to scope docs to this specific thread
    has_documents: bool  # hard gate — if False, knowledge_team route is blocked in code
    route: str
    final_answer: str


# --- Structured routing output -----------------------------------------

class RouteDecision(BaseModel):
    """The CEO must output exactly this schema — no free-form text."""
    route: Literal["knowledge_team", "research_team", "follow_up", "general"]


# --- LLMs --------------------------------------------------------------

_ceo_llm = ChatOpenAI(model="gpt-5.4-mini-2026-03-17", temperature=0)
_followup_llm = ChatOpenAI(model="gpt-5.4-mini-2026-03-17", temperature=0.7)

# Bind structured output once — reuse on every call
_router_llm = _ceo_llm.with_structured_output(RouteDecision)


# --- Node: CEO (Router) ------------------------------------------------

def ceo_node(state: OrchestratorState) -> dict:
    """Analyze the conversation and route to the correct department."""
    history_text = "\n".join(
        f"{m.type.upper()}: {m.content}" for m in state["messages"][:-1]
    )
    routing_messages = [
        SystemMessage(content=ROUTER_SYSTEM),
        HumanMessage(content=(
            f"Conversation so far:\n{history_text}\n\n"
            f"Latest user message: {state['query']}"
            if history_text else
            f"User message: {state['query']}"
        )),
    ]
    # with_structured_output guarantees a valid RouteDecision — no text parsing
    decision: RouteDecision = _router_llm.invoke(routing_messages)
    route = decision.route

    # Hard gate: if the user has never uploaded a document, knowledge_team is unreachable.
    # This cannot be bypassed by prompt injection — it's enforced in Python.
    if route == "knowledge_team" and not state["has_documents"]:
        route = "general"

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
    answer = run_research_team(state["query"], history=state["messages"][:-1])
    return {"final_answer": answer}


# --- Node: General Agent ----------------------------------------------

def general_agent_node(state: OrchestratorState) -> dict:
    """Handles everyday questions with web search — ChatGPT-like experience."""
    answer = run_general_agent(state["query"], state["messages"][:-1])  # history without latest
    return {"final_answer": answer}


# --- Node: Follow-Up Agent --------------------------------------------

def follow_up_node(state: OrchestratorState) -> dict:
    """Handles conversational replies, rephrasing, or summaries using history."""
    agent = create_react_agent(_followup_llm, [], prompt=FOLLOW_UP_SYSTEM)  # no tools — history only
    result = agent.invoke({"messages": state["messages"]})
    answer = result["messages"][-1].content
    return {"final_answer": answer}


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

    # No checkpointer → fully stateless execution
    return builder.compile()


main_graph = _build_main_graph()


# --- Public invoke function -------------------------------------------

def invoke_graph(query: str, history: list[dict], user_id: str, conversation_id: str, has_documents: bool) -> dict:
    """
    history        : list of {"role": "user"|"assistant", "content": "..."} dicts
    user_id        : UUID string from the decoded JWT — used for per-user doc isolation
    conversation_id: UUID string representing the active chat thread
    has_documents  : True only if the conversation has successfully ingested at least one document
    Returns {"answer": str, "route": str}
    """
    from langchain_core.messages import HumanMessage, AIMessage

    messages: list[BaseMessage] = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))

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
