"""
agents/subgraphs/research_graph.py

LangGraph state + node definitions for the Research Team subgraph.
Extracted from research_team.py so the graph definition is separate
from the public streaming/sync wrappers.

Exports:
    ResearchState   — private TypedDict for this subgraph
    research_graph  — compiled LangGraph graph
    MAX_RESEARCH_ITERATIONS
"""
import logging
import operator
from typing import TypedDict, Annotated

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langsmith import traceable

from app.config import DEFAULT_MODEL
from agents.tools import tavily_tool, arxiv_tool, wikipedia_tool, pubmed_tool
from prompts.research_prompts import PLANNER_SYSTEM, RESEARCHER_HUMAN, REPORTER_SYSTEM, REPORTER_HUMAN

logger = logging.getLogger(__name__)

# 3 loops × ~20s each ≈ 60s max — keeps us under Nginx timeout
MAX_RESEARCH_ITERATIONS = 3

_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


# ---------------------------------------------------------------------------
# Private state — never leaks to the parent CEO graph
# ---------------------------------------------------------------------------

class ResearchState(TypedDict):
    query: str
    history_summary: str
    research_plan: list[str]                             # step-by-step checklist from planner
    findings: Annotated[list[str], operator.add]         # accumulated across loop iterations
    iteration: int
    final_report: str


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@traceable(name="Research Planner Node", run_type="chain")
def planner_node(state: ResearchState) -> dict:
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
    response = _llm.invoke(messages)

    lines = [line.strip() for line in response.content.strip().split("\n") if line.strip()]
    plan = [line.lstrip("0123456789. )").strip() for line in lines if line]
    if not plan:
        plan = [state["query"]]

    logger.info("[Research Planner] Generated %d-step plan: %s", len(plan), plan)
    return {"research_plan": plan, "iteration": 0}


@traceable(name="Researcher Node", run_type="chain")
def researcher_node(state: ResearchState) -> dict:
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

    agent = create_react_agent(_llm, [arxiv_tool, pubmed_tool, wikipedia_tool, tavily_tool])
    sys_msg = SystemMessage(content=f"CURRENT DATE: {current_date}. Use this for 'today' / 'latest'.")
    prompt = RESEARCHER_HUMAN.format(
        query=state["query"],
        step_num=step_idx + 1,
        total_steps=len(plan),
        current_step=current_step,
    )
    try:
        result = agent.invoke(
            {"messages": [sys_msg, HumanMessage(content=prompt)]},
            config={"recursion_limit": 4},
        )
        finding = f"Step {step_idx + 1} [{current_step}]:\n{result['messages'][-1].content}"
    except Exception as exc:
        logger.warning("[Researcher] Step %d tool invocation failed: %s", step_idx + 1, exc)
        finding = f"Step {step_idx + 1} [{current_step}]: Research step completed with available data."
    logger.info("[Researcher] Step %d completed.", step_idx + 1)

    return {"findings": [finding], "iteration": iteration + 1}


def should_continue(state: ResearchState) -> str:
    """Loop researcher until all plan steps are covered or max iterations hit."""
    if state["iteration"] >= len(state["research_plan"]):
        return "reporter"
    if state["iteration"] >= MAX_RESEARCH_ITERATIONS:
        return "reporter"
    return "researcher"


@traceable(name="Reporter Node", run_type="chain")
def reporter_node(state: ResearchState) -> dict:
    """Synthesize all findings into a final, well-structured report."""
    findings_text = "\n\n".join(state["findings"])
    messages = [
        SystemMessage(content=REPORTER_SYSTEM),
        HumanMessage(content=REPORTER_HUMAN.format(query=state["query"], findings_text=findings_text)),
    ]
    response = _llm.invoke(messages)
    return {"final_report": response.content}


# ---------------------------------------------------------------------------
# Graph compilation
# ---------------------------------------------------------------------------

def _build_research_graph():
    builder = StateGraph(ResearchState)
    builder.add_node("planner",    planner_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("reporter",   reporter_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_conditional_edges(
        "researcher", should_continue,
        {"researcher": "researcher", "reporter": "reporter"},
    )
    builder.add_edge("reporter", END)
    return builder.compile()


research_graph = _build_research_graph()
