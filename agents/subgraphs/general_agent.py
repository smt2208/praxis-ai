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
from langchain_core.messages import HumanMessage

from agents.tools import tavily_tool
from prompts.general_prompts import GENERAL_SYSTEM


# --- LLM ---------------------------------------------------------------

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)


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

def run_general_agent(query: str, history: list) -> str:
    """
    Entry point for the parent CEO graph.

    Args:
        query  : the user's latest message
        history: list of LangChain BaseMessage objects (injected by CEO)

    Returns the final answer string only — private ReAct steps stay hidden.
    """
    # Include full conversation history so the agent has context
    messages = list(history) + [HumanMessage(content=query)]
    result = _general_agent.invoke({"messages": messages})
    return result["messages"][-1].content
