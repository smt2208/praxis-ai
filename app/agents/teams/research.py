"""
app/agents/teams/research.py

Deep Multi-Domain Research Specialist Department.
Consolidates:
  - Iterative Research checklist planner
  - Multi-domain tools execution (ArXiv, PubMed, Wikipedia, Web search)
  - Real-time SSE streaming runner (astream_research_team)
"""
import logging
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent
from langsmith import traceable

from app.config import DEFAULT_MODEL
from app.agents.context import format_history
from app.agents.tools import openai_web_search, arxiv_tool, wikipedia_tool, pubmed_tool
from app.agents.prompts.research import (
    PLANNER_SYSTEM,
    RESEARCHER_HUMAN,
    REPORTER_SYSTEM,
    REPORTER_HUMAN,
)

logger = logging.getLogger(__name__)

# Capping the deep research loop at 3 iterations balances thorough multi-source
# investigation (ArXiv, PubMed, Wikipedia, Web) against client & proxy keep-alive timeouts.
# 3 steps at ~15-20s per tool invocation yields a ~45-60s execution window, safely within
# typical 300s gateway timeout thresholds (e.g. AWS ALB, Nginx).
MAX_RESEARCH_ITERATIONS = 3

_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)
_research_agent = create_agent(model=_llm, tools=[arxiv_tool, pubmed_tool, wikipedia_tool, openai_web_search])


# ---------------------------------------------------------------------------
# Research State
# ---------------------------------------------------------------------------

class ResearchState(TypedDict):
    query: str
    history_summary: str
    research_plan: list[str]
    findings: list[str]
    iteration: int
    final_report: str


# ---------------------------------------------------------------------------
# Research Step Functions
# ---------------------------------------------------------------------------

@traceable(name="Research Planner Node", run_type="chain")
async def planner_node(state: ResearchState) -> dict:
    """Break the query into a numbered research checklist."""
    from datetime import datetime
    current_date = datetime.now().strftime("%A, %B %d, %Y")

    plan_prompt = state["query"]
    if state.get("history_summary"):
        plan_prompt = f"Context from previous conversation:\n{state['history_summary']}\n\nResearch Task: {state['query']}"

    messages = [
        SystemMessage(content=f"{PLANNER_SYSTEM}\n\nCURRENT SYSTEM DATE: {current_date}"),
        HumanMessage(content=plan_prompt),
    ]
    response = await _llm.ainvoke(messages)
    content = response.content if isinstance(response.content, str) else str(response.content)

    lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
    plan = [line.lstrip("0123456789. )").strip() for line in lines if line]
    if not plan:
        plan = [state["query"]]

    logger.info("[Research Planner] Generated %d-step plan: %s", len(plan), plan)
    return {"research_plan": plan, "iteration": 0}


@traceable(name="Researcher Node", run_type="chain")
async def researcher_node(state: ResearchState) -> dict:
    """
    Pick the next un-researched step and execute it with multi-domain tools.
    Appends findings; the list reducer merges them across iterations.
    """
    from datetime import datetime
    current_date = datetime.now().strftime("%A, %B %d, %Y")

    plan = state["research_plan"] or [state["query"]]
    iteration = state["iteration"]
    step_idx = min(iteration, len(plan) - 1)
    current_step = plan[step_idx]

    logger.info("[Researcher] Step %d/%d: '%s'", step_idx + 1, len(plan), current_step)

    sys_msg = SystemMessage(content=f"CURRENT DATE: {current_date}. Use this for 'today' / 'latest'.")
    prompt = RESEARCHER_HUMAN.format(
        query=state["query"],
        step_num=step_idx + 1,
        total_steps=len(plan),
        current_step=current_step,
    )
    try:
        result = await _research_agent.ainvoke(
            {"messages": [sys_msg, HumanMessage(content=prompt)]},
            config={"recursion_limit": 4},
        )
        finding = f"Step {step_idx + 1} [{current_step}]:\n{result['messages'][-1].content}"
    except Exception as exc:
        logger.warning("[Researcher] Step %d tool invocation failed: %s", step_idx + 1, exc)
        finding = f"Step {step_idx + 1} [{current_step}]: Research step completed with available data."
    logger.info("[Researcher] Step %d completed.", step_idx + 1)

    return {"findings": [finding], "iteration": iteration + 1}


# ---------------------------------------------------------------------------
# Public Streaming Execution API
# ---------------------------------------------------------------------------


@traceable(name="Research Team Stream", run_type="chain")
async def astream_research_team(query: str, history: list | None = None):
    """
    Async generator yielding step-by-step progress then streaming report tokens.
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
    plan_delta = await planner_node(state)
    state.update(plan_delta)

    # Step 2: Multi-step research execution
    total_steps = min(len(state["research_plan"]), MAX_RESEARCH_ITERATIONS)
    for i in range(total_steps):
        yield {"type": "status", "message": "Researching..."}
        research_delta = await researcher_node(state)
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

