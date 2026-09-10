"""
app/agents/teams/general.py

General Agent — Everyday queries, knowledge, how-to guides, and web search.
"""
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from app.config import DEFAULT_MODEL
from app.agents.tools import openai_web_search, openai_news_search
from app.agents.prompts.general import GENERAL_SYSTEM

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.2)


def _build_general_agent():
    from langchain.agents import create_agent
    return create_agent(
        model=_llm,
        tools=[openai_web_search, openai_news_search],
        system_prompt=GENERAL_SYSTEM,
    )


_general_agent = _build_general_agent()


@traceable(name="General Agent Stream", run_type="chain")
async def astream_general_agent(query: str, history: list, user_tz: str | None = None):
    """Async generator yielding LLM token strings in real-time."""
    from app.agents.tools import get_current_time_str

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

            # Filter 1: Ignore raw tool outputs (e.g. raw web search JSON results).
            # These are internal to the agent loop and must not be leaked into the user SSE stream.
            msg_type = getattr(message_chunk, "type", None)
            if msg_type in ("tool", "function"):
                continue

            # Filter 2: Ignore tool call invocation chunks (the LLM's internal JSON instructions to invoke a tool).
            # Only the final natural-language synthesis tokens should be yielded to the client.
            if getattr(message_chunk, "tool_call_chunks", None) or getattr(message_chunk, "tool_calls", None):
                continue

            content = message_chunk.content
            if isinstance(content, str) and content:
                yield content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                        yield block["text"]

