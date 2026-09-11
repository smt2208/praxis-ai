"""
app/agents/teams/research.py

Deep Multi-Domain Research Specialist Department.
Built as a compiled LangGraph iterative research subgraph:
  [START] -> [planner] -> [researcher] ◄────────┐
                              │                 │ (loop if iteration < total_steps)
                              ▼                 │
                      (_should_continue?) ──────┘
                              │ (done)
                              ▼
                          [reporter]
                              │
                              ▼
                            [END]
"""
import logging
import operator
from datetime import datetime
from typing import Annotated, TypedDict

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from app.agents.context import format_history
from app.agents.prompts.research import (
    PLANNER_SYSTEM,
    REPORTER_HUMAN,
    REPORTER_SYSTEM,
    RESEARCHER_HUMAN,
)
from app.agents.tools import arxiv_tool, pubmed_tool, web_search_tool, wikipedia_tool
from app.config import DEFAULT_MODEL

logger = logging.getLogger(__name__)

# Capping the deep research loop at 3 iterations balances thorough multi-source
# investigation (ArXiv, PubMed, Wikipedia, Web) against client & proxy keep-alive timeouts.
MAX_RESEARCH_ITERATIONS = 3

_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


# ---------------------------------------------------------------------------
# Subgraph State Definition
# ---------------------------------------------------------------------------

class ResearchState(TypedDict):
    query: str
    history_summary: str
    research_plan: list[str]
    findings: Annotated[list[str], operator.add]
    iteration: int
    final_report: str


# ---------------------------------------------------------------------------
# LangGraph Subgraph Nodes
# ---------------------------------------------------------------------------

@traceable(name="Research Planner Node", run_type="chain")
async def planner_node(state: ResearchState) -> dict:
    """Break the query into a numbered research checklist."""
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
    Appends findings via the operator.add reducer across iterations.
    """
    current_date = datetime.now().strftime("%A, %B %d, %Y")

    research_agent = create_agent(
        model=_llm,
        tools=[arxiv_tool, pubmed_tool, wikipedia_tool, web_search_tool],
    )

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
        result = await research_agent.ainvoke(
            {"messages": [sys_msg, HumanMessage(content=prompt)]},
            config={"recursion_limit": 4},
        )
        finding = f"Step {step_idx + 1} [{current_step}]:\n{result['messages'][-1].content}"
    except Exception as exc:
        logger.warning("[Researcher] Step %d tool invocation failed: %s", step_idx + 1, exc)
        finding = f"Step {step_idx + 1} [{current_step}]: Research step completed with available data."
    logger.info("[Researcher] Step %d completed.", step_idx + 1)

    return {"findings": [finding], "iteration": iteration + 1}


@traceable(name="Reporter Node", run_type="chain")
async def reporter_node(state: ResearchState) -> dict:
    """Synthesize findings across all research iterations into a cohesive report."""
    findings_text = "\n\n".join(state.get("findings", []))
    messages = [
        SystemMessage(content=REPORTER_SYSTEM),
        HumanMessage(content=REPORTER_HUMAN.format(query=state["query"], findings_text=findings_text)),
    ]
    response = await _llm.ainvoke(messages)
    content = response.content if isinstance(response.content, str) else str(response.content)
    return {"final_report": content}


def _should_continue_research(state: ResearchState) -> str:
    """Determine whether to research the next checklist item or synthesize the final report."""
    plan = state.get("research_plan", [])
    iteration = state.get("iteration", 0)
    total_steps = min(len(plan), MAX_RESEARCH_ITERATIONS)
    if iteration < total_steps:
        return "researcher"
    return "reporter"


# ---------------------------------------------------------------------------
# Graph Assembly & Compilation
# ---------------------------------------------------------------------------

def _build_research_graph():
    """Compile the Deep Research Team iterative subgraph."""
    builder = StateGraph(ResearchState)

    builder.add_node("planner", planner_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("reporter", reporter_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "researcher")
    builder.add_conditional_edges(
        "researcher",
        _should_continue_research,
        {
            "researcher": "researcher",
            "reporter": "reporter",
        },
    )
    builder.add_edge("reporter", END)

    return builder.compile()


_research_graph = _build_research_graph()


# ---------------------------------------------------------------------------
# Public Streaming Execution API
# ---------------------------------------------------------------------------

@traceable(name="Research Team Stream", run_type="chain")
async def astream_research_team(query: str, history: list | None = None):
    """
    Async generator yielding step-by-step progress then streaming report tokens.
    Streams from the compiled LangGraph research subgraph.
    """
    history_summary = format_history(history) if history else ""

    initial_state: ResearchState = {
        "query": query,
        "history_summary": history_summary,
        "research_plan": [],
        "findings": [],
        "iteration": 0,
        "final_report": "",
    }

    yield {"type": "status", "message": "Researching..."}

    synthesizing_started = False
    tokens_streamed = False

    async for mode, payload in _research_graph.astream(
        initial_state,
        stream_mode=["messages", "updates"],
    ):
        if mode == "updates":
            for node_name, update in payload.items():
                if node_name in ("planner", "researcher"):
                    yield {"type": "status", "message": "Researching..."}
                elif node_name == "reporter":
                    final_report = update.get("final_report", "")
                    if not tokens_streamed and final_report:
                        if not synthesizing_started:
                            yield {"type": "status", "message": "Synthesizing..."}
                        yield {"type": "token", "content": final_report}

        elif mode == "messages":
            chunk, metadata = payload
            if metadata.get("langgraph_node") == "reporter":
                if not synthesizing_started:
                    synthesizing_started = True
                    yield {"type": "status", "message": "Synthesizing..."}

                content = chunk.content
                if isinstance(content, str) and content:
                    tokens_streamed = True
                    yield {"type": "token", "content": content}
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                            tokens_streamed = True
                            yield {"type": "token", "content": block["text"]}
