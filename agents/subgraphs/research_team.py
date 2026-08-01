"""
agents/subgraphs/research_team.py

Public entry points for the Research Team department.
Heavy implementation is split into:
  - research_graph.py  → LangGraph state + nodes + compiled graph

This file only contains:
  run_research_team      — synchronous wrapper (called by LangGraph CEO node)
  astream_research_team  — async streaming generator (called by SSE endpoint)
"""
import asyncio
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from app.config import DEFAULT_MODEL
from agents.utils import format_history
from agents.subgraphs.research_graph import (
    research_graph, ResearchState,
    planner_node, researcher_node,
    MAX_RESEARCH_ITERATIONS,
)
from prompts.research_prompts import REPORTER_SYSTEM, REPORTER_HUMAN

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


# ---------------------------------------------------------------------------
# Synchronous wrapper — called by the CEO LangGraph node
# ---------------------------------------------------------------------------

@traceable(name="Research Team Run", run_type="chain")
def run_research_team(query: str, history: list = None) -> str:
    """Entry point for synchronous invocation from the CEO node."""
    history_summary = format_history(history) if history else ""

    result = research_graph.invoke({
        "query": query,
        "history_summary": history_summary,
        "research_plan": [],
        "findings": [],
        "iteration": 0,
        "final_report": "",
    })
    return result["final_report"]


# ---------------------------------------------------------------------------
# Async streaming generator — called by the SSE chat endpoint
# ---------------------------------------------------------------------------

@traceable(name="Research Team Stream", run_type="chain")
async def astream_research_team(query: str, history: list = None):
    """
    Async generator yielding step-by-step progress then streaming report tokens.
    Yields dicts:
        {"type": "status", "message": "..."}
        {"type": "token",  "content": "..."}
    """
    history_summary = format_history(history) if history else ""

    state: ResearchState = {
        "query": query,
        "history_summary": history_summary,
        "research_plan": [],
        "findings": [],
        "iteration": 0,
        "final_report": "",
    }

    # Step 1: Planning
    yield {"type": "status", "message": "Researching..."}
    plan_delta = await asyncio.to_thread(planner_node, state)
    state.update(plan_delta)

    # Step 2: Multi-step research execution
    total_steps = min(len(state["research_plan"]), MAX_RESEARCH_ITERATIONS)
    for i in range(total_steps):
        yield {"type": "status", "message": "Researching..."}
        research_delta = await asyncio.to_thread(researcher_node, state)
        state["findings"].extend(research_delta.get("findings", []))
        state["iteration"] = research_delta.get("iteration", i + 1)

    # Step 3: Synthesis with live token streaming
    yield {"type": "status", "message": "Synthesizing..."}

    findings_text = "\n\n".join(state["findings"])
    messages = [
        SystemMessage(content=REPORTER_SYSTEM),
        HumanMessage(content=REPORTER_HUMAN.format(query=state["query"], findings_text=findings_text)),
    ]

    async for chunk in _llm.astream(messages):
        content = chunk.content
        if isinstance(content, str) and content:
            yield {"type": "token", "content": content}
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                    yield {"type": "token", "content": block["text"]}
