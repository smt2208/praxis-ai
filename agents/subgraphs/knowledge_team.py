"""
agents/subgraphs/knowledge_team.py

Public entry points for the Knowledge Team department.
Heavy implementation is split across:
  - knowledge_graph.py  → LangGraph state + nodes + compiled graph
  - knowledge_rag.py    → query rewriting + doc-context evaluation helpers

This file only contains:
  run_knowledge_team      — synchronous wrapper (called by LangGraph CEO node)
  astream_knowledge_team  — async streaming generator (called by SSE endpoint)
"""
import asyncio
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from app.config import DEFAULT_MODEL
from agents.utils import format_history
from agents.tools import tavily_tool
from agents.subgraphs.knowledge_graph import knowledge_graph, KnowledgeState
from agents.subgraphs.knowledge_rag import rewrite_query, evaluate_doc_context
from prompts.knowledge_prompts import SYNTHESIZER_SYSTEM, SYNTHESIZER_HUMAN

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)


# ---------------------------------------------------------------------------
# Synchronous wrapper — called by the CEO LangGraph node
# ---------------------------------------------------------------------------

@traceable(name="Knowledge Team Run", run_type="chain")
def run_knowledge_team(query: str, user_id: str, conversation_id: str, history: list = None) -> str:
    """Entry point for synchronous graph invocation from the CEO node."""
    history_summary = format_history(history)
    standalone_query = rewrite_query(query, history_summary)

    result = knowledge_graph.invoke({
        "query": standalone_query,
        "history_summary": history_summary,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "rag_results": "",
        "web_results": "",
        "final_answer": "",
        "critic_feedback": "",
        "retry_count": 0,
    })
    return result["final_answer"]


# ---------------------------------------------------------------------------
# Async streaming generator — called by the SSE chat endpoint
# ---------------------------------------------------------------------------

@traceable(name="Knowledge Team Stream", run_type="chain")
async def astream_knowledge_team(query: str, user_id: str, conversation_id: str, history: list = None):
    """
    Enterprise RAG streaming: yields progress events then synthesizer tokens.
    Yields dicts:
        {"type": "status", "message": "..."}
        {"type": "token",  "content": "..."}
    """
    from langgraph.prebuilt import create_react_agent

    history_summary = format_history(history)

    # Step 1: Query rewriting
    yield {"type": "status", "message": "Analyzing query..."}
    standalone_query = await asyncio.to_thread(rewrite_query, query, history_summary)

    state: KnowledgeState = {
        "query": standalone_query,
        "history_summary": history_summary,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "rag_results": "",
        "web_results": "",
        "final_answer": "",
        "critic_feedback": "",
        "retry_count": 0,
    }

    # Step 2: Document retrieval
    yield {"type": "status", "message": "Searching documents..."}
    from agents.tools import build_hybrid_retriever
    rag_tool = build_hybrid_retriever(user_id=user_id, conversation_id=conversation_id)

    async def _fetch_rag() -> str:
        agent = create_react_agent(_llm, [rag_tool])
        result = await agent.ainvoke({"messages": [HumanMessage(content=standalone_query)]}, config={"recursion_limit": 4})
        return result["messages"][-1].content

    try:
        state["rag_results"] = await _fetch_rag()
    except Exception as exc:
        state["rag_results"] = f"Document retrieval error: {exc}"

    # Step 3: Adaptive web search gate
    yield {"type": "status", "message": "Thinking..."}
    is_sufficient = await asyncio.to_thread(evaluate_doc_context, standalone_query, state["rag_results"])

    if not is_sufficient:
        yield {"type": "status", "message": "Searching web..."}

        async def _fetch_web() -> str:
            agent = create_react_agent(_llm, [tavily_tool])
            from datetime import datetime
            date_str = datetime.now().strftime("%A, %B %d, %Y")
            sys_msg = SystemMessage(content=f"CURRENT DATE: {date_str}. Use this as reference for 'today' or 'latest'.")
            result = await agent.ainvoke(
                {"messages": [sys_msg, HumanMessage(content=f"Search for: {standalone_query}")]},
                config={"recursion_limit": 4},
            )
            return result["messages"][-1].content

        try:
            state["web_results"] = await _fetch_web()
        except Exception:
            state["web_results"] = ""

    # Step 4: Grounded synthesis with live token streaming
    yield {"type": "status", "message": "Thinking..."}

    human_content = SYNTHESIZER_HUMAN.format(
        query=query,
        rag_results=state["rag_results"],
        web_results=state["web_results"] or "None required (internal document context was complete).",
    )
    messages = [SystemMessage(content=SYNTHESIZER_SYSTEM), HumanMessage(content=human_content)]

    async for chunk in _llm.astream(messages):
        content = chunk.content
        if isinstance(content, str) and content:
            yield {"type": "token", "content": content}
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                    yield {"type": "token", "content": block["text"]}
