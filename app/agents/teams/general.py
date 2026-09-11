"""
app/agents/teams/general.py

General Agent — Everyday queries, knowledge, how-to guides, and web search.

Uses a LangGraph subgraph with llm.bind_tools() + ToolNode instead of a
create_agent ReAct loop. This enables native JSON function calling (faster,
more reliable) and gives full control over the streaming path.

Subgraph structure:
    [START] → [call_model] → (tools_condition)
                 ↑                  │ tool calls present
                 │                  ▼
                 └───────────── [tools]
                  (loop back)
                 no more tool calls → [END]
"""
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langsmith import traceable

from app.agents.prompts.general import GENERAL_SYSTEM
from app.agents.tools import web_search_tool
from app.config import DEFAULT_MODEL

logger = logging.getLogger(__name__)

# --- LLM and tool binding ---------------------------------------------------

_general_tools = [web_search_tool]
_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.2)
_llm_with_tools = _llm.bind_tools(_general_tools)


# --- Subgraph node ----------------------------------------------------------

async def _call_model_node(state: MessagesState) -> dict:
    """
    Core LLM node. Receives the full message history and returns either:
      - A final AI response (no tool calls → tools_condition routes to END), or
      - A tool-call request (tools_condition routes to ToolNode for execution).
    The static system prompt is prepended on every call so the LLM always has its persona.
    """
    messages = [SystemMessage(content=GENERAL_SYSTEM)] + state["messages"]
    response = await _llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


# --- Subgraph compilation ---------------------------------------------------

def _build_general_graph():
    """
    Compile the General Agent as a self-contained LangGraph subgraph using
    MessagesState (standard list of BaseMessage objects).
    """
    builder = StateGraph(MessagesState)

    builder.add_node("call_model", _call_model_node)
    builder.add_node("tools", ToolNode(_general_tools))

    builder.add_edge(START, "call_model")
    # tools_condition: if last message has tool calls → "tools"; else → END
    builder.add_conditional_edges("call_model", tools_condition)
    # After tool execution, loop back to synthesize the results
    builder.add_edge("tools", "call_model")

    return builder.compile()


_general_graph = _build_general_graph()


# --- Public streaming API ---------------------------------------------------

@traceable(name="General Agent Stream", run_type="chain")
async def astream_general_agent(query: str, history: list, user_tz: str | None = None):
    """
    Async generator yielding LLM token strings in real-time for SSE.

    Streams from the compiled general subgraph using stream_mode="messages",
    which yields individual message chunks as the LLM generates them.
    Tool result messages are filtered out so only final synthesized AI text
    tokens reach the client SSE stream.
    """
    from app.agents.tools import get_current_time_str

    current_time = get_current_time_str(user_tz)
    time_msg = SystemMessage(
        content=(
            f"CURRENT SYSTEM TIME: {current_time}. "
            "IMPORTANT: Always use this date as your reference for 'today', 'latest news', or current events."
        )
    )

    # Build input: time context + prior history + new user query
    messages = [time_msg] + list(history) + [HumanMessage(content=query)]

    async for mode, chunk in _general_graph.astream(
        {"messages": messages},
        stream_mode=["messages"],
    ):
        if mode != "messages":
            continue

        message_chunk, _metadata = chunk

        # Filter 1: Skip raw tool result messages (ToolMessage objects).
        # These are internal to the agent loop and must not appear in the user SSE stream.
        msg_type = getattr(message_chunk, "type", None)
        if msg_type in ("tool", "function"):
            continue

        # Filter 2: Skip LLM chunks that are generating a tool call JSON payload.
        # These are structured function-call instructions, not human-readable text.
        if getattr(message_chunk, "tool_call_chunks", None) or getattr(message_chunk, "tool_calls", None):
            continue

        content = message_chunk.content
        if isinstance(content, str) and content:
            yield content
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                    yield block["text"]

