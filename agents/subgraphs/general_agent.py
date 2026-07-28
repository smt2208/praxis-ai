"""
agents/subgraphs/general_agent.py

General Agent — the "ChatGPT-like" department.

Handles everyday questions, general knowledge, how-to guides,
explanations, and anything that doesn't need internal docs or
deep academic research.

Tools:
  - Tavily web search (for live facts, current events, prices, etc.)

Design: A single ReAct agent that decides for itself whether to
search the web or answer from its own knowledge. Simple and fast.
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from agents.tools import tavily_tool
from prompts.general_prompts import GENERAL_SYSTEM


# --- LLM ---------------------------------------------------------------

_llm = ChatOpenAI(model="gpt-5.4-mini-2026-03-17", temperature=0.2)


# --- Agent (built once, reused on every call) --------------------------

def _build_general_agent():
    from langgraph.prebuilt import create_react_agent
    return create_react_agent(
        _llm,
        tools=[tavily_tool],
        prompt=GENERAL_SYSTEM,   # Injected as the system message
    )


_general_agent = _build_general_agent()


# --- Wrapper (called by parent graph) ----------------------------------

def run_general_agent(query: str, history: list, user_tz: str = None) -> str:
    """
    Entry point for the parent CEO graph.

    Args:
        query  : the user's latest message
        history: list of LangChain BaseMessage objects (injected by CEO)
        user_tz: optional user IANA timezone string (e.g. 'Asia/Tokyo')

    Returns the final answer string only — private ReAct steps stay hidden.
    """
    from agents.tools import get_current_time_str
    current_time = get_current_time_str(user_tz)
    time_msg = SystemMessage(content=f"CURRENT SYSTEM TIME: {current_time}. IMPORTANT: Always use this date as your reference for 'today', 'latest news', or current events.")

    # Include full conversation history so the agent has context
    messages = [time_msg] + list(history) + [HumanMessage(content=query)]
    result = _general_agent.invoke({"messages": messages}, config={"recursion_limit": 4})
    return result["messages"][-1].content


async def astream_general_agent(query: str, history: list, user_tz: str = None):
    """Async generator yielding LLM token strings in real-time."""
    from agents.tools import get_current_time_str
    current_time = get_current_time_str(user_tz)
    time_msg = SystemMessage(content=f"CURRENT SYSTEM TIME: {current_time}. IMPORTANT: Always use this date as your reference for 'today', 'latest news', or current events.")

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


