"""
agents/subgraphs/knowledge_team.py

Department A — External Knowledge Team
Workflow: RAG Agent → Web Expert → Synthesizer

Private state never leaks to the parent CEO graph.
"""
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent

from agents.tools import tavily_tool
from prompts.knowledge_prompts import WEB_EXPERT_PROMPT, SYNTHESIZER_SYSTEM, SYNTHESIZER_HUMAN


# --- Private state (isolated from parent) ------------------------------

class KnowledgeState(TypedDict):
    query: str
    rag_results: str
    web_results: str
    final_answer: str


# --- LLM ---------------------------------------------------------------

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# --- Node: RAG Agent ---------------------------------------------------

def rag_agent_node(state: KnowledgeState) -> dict:
    """Search private knowledge base first."""
    # Import here to avoid circular init; retriever_tool is built lazily
    from agents.tools import build_hybrid_retriever
    # Use a cached version if available on module
    if not hasattr(rag_agent_node, "_tool"):
        rag_agent_node._tool = build_hybrid_retriever()

    agent = create_react_agent(_llm, [rag_agent_node._tool])
    result = agent.invoke({"messages": [HumanMessage(content=state["query"])]})
    answer = result["messages"][-1].content
    return {"rag_results": answer}


# --- Node: Web Expert --------------------------------------------------

def web_expert_node(state: KnowledgeState) -> dict:
    """Supplement RAG results with fresh web information via Tavily."""
    agent = create_react_agent(_llm, [tavily_tool])
    prompt = WEB_EXPERT_PROMPT.format(
        query=state['query'],
        rag_results=state['rag_results']
    )
    result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    answer = result["messages"][-1].content
    return {"web_results": answer}


# --- Node: Synthesizer -------------------------------------------------

def synthesizer_node(state: KnowledgeState) -> dict:
    """Merge RAG + web results into one clean, cited answer."""
    messages = [
        SystemMessage(content=SYNTHESIZER_SYSTEM),
        HumanMessage(content=SYNTHESIZER_HUMAN.format(
            query=state['query'],
            rag_results=state['rag_results'],
            web_results=state['web_results']
        )),
    ]
    response = _llm.invoke(messages)
    return {"final_answer": response.content}


# --- Build subgraph ----------------------------------------------------

def _build_knowledge_graph():
    builder = StateGraph(KnowledgeState)
    builder.add_node("rag_agent", rag_agent_node)
    builder.add_node("web_expert", web_expert_node)
    builder.add_node("synthesizer", synthesizer_node)

    builder.add_edge(START, "rag_agent")
    builder.add_edge("rag_agent", "web_expert")
    builder.add_edge("web_expert", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile()


knowledge_graph = _build_knowledge_graph()


# --- Wrapper (called by parent graph) ----------------------------------

def run_knowledge_team(query: str) -> str:
    """
    Entry point for the parent CEO graph.
    Returns only the final answer string.
    """
    result = knowledge_graph.invoke({"query": query, "rag_results": "", "web_results": "", "final_answer": ""})
    return result["final_answer"]
