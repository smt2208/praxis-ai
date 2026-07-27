"""
agents/subgraphs/research_team.py

Department B — Deep Thinking / Academic Research Team
Workflow: Planner → Researcher (loops up to MAX_ITER times) → Reporter

Private state never leaks to the parent CEO graph.
"""
from typing import TypedDict, Annotated
import operator
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent

from agents.tools import tavily_tool, arxiv_tool, wikipedia_tool, pubmed_tool
from prompts.research_prompts import PLANNER_SYSTEM, RESEARCHER_HUMAN, REPORTER_SYSTEM, REPORTER_HUMAN


# --- Constants ---------------------------------------------------------
MAX_RESEARCH_ITERATIONS = 3   # 3 loops × ~20s each ≈ 60s max — keeps us under Nginx timeout


# --- Private state -----------------------------------------------------

class ResearchState(TypedDict):
    query: str
    history_summary: str
    research_plan: list[str]          # Step-by-step checklist from planner
    findings: Annotated[list[str], operator.add]  # Accumulated, appended each loop
    iteration: int
    final_report: str


# --- LLM ---------------------------------------------------------------

_llm = ChatOpenAI(model="gpt-5.4-mini-2026-03-17", temperature=0)


# --- Node: Planner -----------------------------------------------------

def planner_node(state: ResearchState) -> dict:
    """Break the query into a numbered research checklist."""
    plan_prompt = state["query"]
    if state.get("history_summary"):
        plan_prompt = f"Context from previous conversation:\n{state['history_summary']}\n\nResearch Task: {state['query']}"

    messages = [
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(content=plan_prompt),
    ]
    response = _llm.invoke(messages)
    # Parse numbered list into python list
    lines = [line.strip() for line in response.content.strip().split("\n") if line.strip()]
    plan = [line.lstrip("0123456789. )").strip() for line in lines if line]
    if not plan:
        plan = [state["query"]]
    print(f"[Deep Research Agent] Generated research plan with {len(plan)} steps: {plan}", flush=True)
    return {"research_plan": plan, "iteration": 0}


# --- Node: Researcher --------------------------------------------------

def researcher_node(state: ResearchState) -> dict:
    """
    Pick the next un-researched step and search for it.
    Appends findings (list reducer merges them).
    """
    # Determine which step to work on based on iteration count
    plan = state["research_plan"]
    if not plan:
        plan = [state["query"]]
    iteration = state["iteration"]
    step_idx = min(iteration, len(plan) - 1)
    current_step = plan[step_idx]

    print(f"[Deep Research Agent] Executing Step {step_idx + 1}/{len(plan)}: '{current_step}'", flush=True)
    # Deep Agent equipped with multi-domain research tools (Academic, Medical, Encyclopedic, Web)
    agent = create_react_agent(_llm, [arxiv_tool, pubmed_tool, wikipedia_tool, tavily_tool])
    prompt = RESEARCHER_HUMAN.format(
        query=state['query'],
        step_num=step_idx + 1,
        total_steps=len(plan),
        current_step=current_step
    )
    # recursion_limit=4 prevents runaway tool-calling loops
    result = agent.invoke({"messages": [HumanMessage(content=prompt)]}, config={"recursion_limit": 4})
    finding = f"Step {step_idx + 1} [{current_step}]:\n{result['messages'][-1].content}"
    print(f"[Deep Research Agent] Step {step_idx + 1} completed.", flush=True)

    return {
        "findings": [finding],
        "iteration": iteration + 1,
    }


# --- Routing: continue or finish? --------------------------------------

def should_continue(state: ResearchState) -> str:
    """Loop researcher until all plan steps are covered or max iterations hit."""
    if state["iteration"] >= len(state["research_plan"]):
        return "reporter"
    if state["iteration"] >= MAX_RESEARCH_ITERATIONS:
        return "reporter"
    return "researcher"


# --- Node: Reporter ----------------------------------------------------

def reporter_node(state: ResearchState) -> dict:
    """Synthesize all findings into a final, well-structured report."""
    findings_text = "\n\n".join(state["findings"])
    messages = [
        SystemMessage(content=REPORTER_SYSTEM),
        HumanMessage(content=REPORTER_HUMAN.format(
            query=state['query'],
            findings_text=findings_text
        )),
    ]
    response = _llm.invoke(messages)
    return {"final_report": response.content}


# --- Build subgraph ----------------------------------------------------

def _build_research_graph():
    builder = StateGraph(ResearchState)
    builder.add_node("planner", planner_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("reporter", reporter_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_conditional_edges("researcher", should_continue, {"researcher": "researcher", "reporter": "reporter"})
    builder.add_edge("reporter", END)

    return builder.compile()


research_graph = _build_research_graph()


# --- Wrapper (called by parent graph) ----------------------------------

def run_research_team(query: str, history: list = None) -> str:
    """
    Entry point for the parent CEO graph.
    Returns only the final report string.
    """
    history_summary = ""
    if history:
        history_summary = "\n".join(f"{m.type.upper()}: {m.content}" for m in history[-4:])

    result = research_graph.invoke({
        "query": query,
        "history_summary": history_summary,
        "research_plan": [],
        "findings": [],
        "iteration": 0,
        "final_report": "",
    })
    return result["final_report"]
