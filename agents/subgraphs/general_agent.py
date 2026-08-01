"""
agents/subgraphs/general_agent.py

General Agent — the "ChatGPT-like" department.

Handles everyday questions, general knowledge, how-to guides,
explanations, and anything that doesn't need internal docs or
deep academic research.

Tools:
  - Tavily web search (for live facts, current events, prices, etc.)
  - Tavily news search (dedicated news index for breaking news, sports, etc.)

Design: A single ReAct agent that decides for itself whether to
search the web or answer from its own knowledge. Simple and fast.
"""
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from app.config import DEFAULT_MODEL
from agents.tools import tavily_tool, tavily_news_tool
from prompts.general_prompts import GENERAL_SYSTEM

logger = logging.getLogger(__name__)


# --- LLM ---------------------------------------------------------------

_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.2)


# --- Agent (built once, reused on every call) --------------------------

def _build_general_agent():
    from langgraph.prebuilt import create_react_agent
    return create_react_agent(
        _llm,
        tools=[tavily_tool, tavily_news_tool],
        prompt=GENERAL_SYSTEM,
    )


_general_agent = _build_general_agent()


# --- Wrapper (called by parent graph) ----------------------------------

@traceable(name="General Agent Run", run_type="chain")
def run_general_agent(query: str, history: list, user_tz: str = None) -> str:
    """
    Entry point for the parent CEO graph.
    Returns the final answer string only — private ReAct steps stay hidden.
    """
    from agents.tools import get_current_time_str

    current_time = get_current_time_str(user_tz)
    time_msg = SystemMessage(
        content=f"CURRENT SYSTEM TIME: {current_time}. IMPORTANT: Always use this date as your reference for 'today', 'latest news', or current events."
    )

    messages = [time_msg] + list(history) + [HumanMessage(content=query)]
    result = _general_agent.invoke({"messages": messages}, config={"recursion_limit": 4})
    return result["messages"][-1].content


@traceable(name="General Agent Stream", run_type="chain")
async def astream_general_agent(query: str, history: list, user_tz: str = None):
    """Async generator yielding LLM token strings in real-time."""
    from agents.tools import get_current_time_str

    current_time = get_current_time_str(user_tz)
    time_msg = SystemMessage(
        content=f"CURRENT SYSTEM TIME: {current_time}. IMPORTANT: Always use this date as your reference for 'today', 'latest news', or current events."
    )

    messages = [time_msg] + list(history) + [HumanMessage(content=query)]
    async for mode, chunk in _general_agent.astream(
        {"messages": messages},
        config={"recursion_limit": 4},
        stream_mode=["messages"],
    ):
        if mode == "messages":
            message_chunk, metadata = chunk

            # Ignore raw tool output messages (e.g. Tavily search result JSON)
            msg_type = getattr(message_chunk, "type", None)
            if msg_type in ("tool", "function"):
                continue

            # Ignore tool call invocation chunks (LLM calling tools)
            if getattr(message_chunk, "tool_call_chunks", None) or getattr(message_chunk, "tool_calls", None):
                continue

            content = message_chunk.content
            if isinstance(content, str) and content:
                yield content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                        yield block["text"]
