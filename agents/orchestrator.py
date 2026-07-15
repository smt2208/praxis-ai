"""
agents/orchestrator.py

The CEO — main stateless LangGraph orchestrator.
Reads injected chat history, routes to the right department,
and returns the final answer. No checkpointer — fully stateless.
"""
from typing import TypedDict, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from typing import Annotated

from agents.subgraphs.knowledge_team import run_knowledge_team
from agents.subgraphs.research_team import run_research_team
from prompts.orchestrator_prompts import ROUTER_SYSTEM


# --- Orchestrator state (shared across all top-level nodes) ------------

class OrchestratorState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    query: str
    route: str
    final_answer: str


# --- LLMs --------------------------------------------------------------

_ceo_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
_followup_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

# Routing choices as a Literal for structured output
_ROUTES = Literal["knowledge_team", "research_team", "follow_up"]


# --- Node: CEO (Router) ------------------------------------------------

def ceo_node(state: OrchestratorState) -> dict:
    """Analyze the conversation and route to the correct department."""
    # Build routing prompt with full history context
    history_text = "\n".join(
        f"{m.type.upper()}: {m.content}" for m in state["messages"][:-1]  # all but latest
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
    response = _ceo_llm.invoke(routing_messages)
    route = response.content.strip().lower()

    # Fallback safety
    if route not in ("knowledge_team", "research_team", "follow_up"):
        route = "knowledge_team"

    return {"route": route}


# --- Node: Knowledge Team wrapper --------------------------------------

def knowledge_team_node(state: OrchestratorState) -> dict:
    answer = run_knowledge_team(state["query"])
    return {"final_answer": answer}


# --- Node: Research Team wrapper ---------------------------------------

def research_team_node(state: OrchestratorState) -> dict:
    answer = run_research_team(state["query"])
    return {"final_answer": answer}


# --- Node: Follow-Up Agent --------------------------------------------

def follow_up_node(state: OrchestratorState) -> dict:
    """Handles conversational replies, rephrasing, or summaries using history."""
    agent = create_react_agent(_followup_llm, [])  # no tools — history only
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
    builder.add_node("follow_up_node", follow_up_node)

    builder.add_edge(START, "ceo")
    builder.add_conditional_edges(
        "ceo",
        route_to_department,
        {
            "knowledge_team": "knowledge_team_node",
            "research_team": "research_team_node",
            "follow_up": "follow_up_node",
        },
    )
    builder.add_edge("knowledge_team_node", END)
    builder.add_edge("research_team_node", END)
    builder.add_edge("follow_up_node", END)

    # No checkpointer → fully stateless execution
    return builder.compile()


main_graph = _build_main_graph()


# --- Public invoke function -------------------------------------------

def invoke_graph(query: str, history: list[dict]) -> dict:
    """
    history: list of {"role": "user"|"assistant", "content": "..."} dicts
    Returns {"answer": str, "route": str}
    """
    from langchain_core.messages import HumanMessage, AIMessage

    # Convert history dicts → LangChain messages
    messages: list[BaseMessage] = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))

    # Append latest user message
    messages.append(HumanMessage(content=query))

    result = main_graph.invoke({
        "messages": messages,
        "query": query,
        "route": "",
        "final_answer": "",
    })

    return {
        "answer": result["final_answer"],
        "route": result["route"],
    }
