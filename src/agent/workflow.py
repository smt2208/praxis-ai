from typing import Annotated, TypedDict, List, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage, AIMessage
from src.agent.tools import tavily_search, generate_and_upload_document, search_uploaded_documents, execute_python_and_visualize
from src.agent.prompts import (
    RESEARCHER_PROMPT,
    KNOWLEDGE_VAULT_PROMPT,
    DOCUMENT_GENERATOR_PROMPT,
    CODE_SANDBOX_PROMPT,
    SUPERVISOR_PROMPT
)
from src.core.config import settings
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import ToolNode
import json

# Define State
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    model_name: str
    user_id: str
    conversation_id: str
    active_agent: str

def get_llm(model_name: str):
    if "gemini" in model_name.lower():
        model_id = "gemini-1.5-flash" if "flash" in model_name.lower() else model_name
        return ChatGoogleGenerativeAI(model=model_id, google_api_key=settings.google_api_key)
    else:
        return ChatOpenAI(model=model_name, api_key=settings.openai_api_key)

# ---------------------------------------------------------
# SWARM AGENTS (Workers)
# Each agent is a specialized LLM with access to only 1 tool
# ---------------------------------------------------------

async def researcher_agent(state: AgentState):
    llm = get_llm(state["model_name"]).bind_tools([tavily_search])
    sys_msg = SystemMessage(content=RESEARCHER_PROMPT)
    response = await llm.ainvoke([sys_msg] + state["messages"])
    return {"messages": [response], "active_agent": "researcher"}

async def knowledge_vault_agent(state: AgentState):
    llm = get_llm(state["model_name"]).bind_tools([search_uploaded_documents])
    sys_msg = SystemMessage(content=KNOWLEDGE_VAULT_PROMPT)
    response = await llm.ainvoke([sys_msg] + state["messages"])
    return {"messages": [response], "active_agent": "knowledge_vault"}

async def document_generator_agent(state: AgentState):
    llm = get_llm(state["model_name"]).bind_tools([generate_and_upload_document])
    sys_msg = SystemMessage(content=DOCUMENT_GENERATOR_PROMPT)
    response = await llm.ainvoke([sys_msg] + state["messages"])
    return {"messages": [response], "active_agent": "document_generator"}

async def code_sandbox_agent(state: AgentState):
    llm = get_llm(state["model_name"]).bind_tools([execute_python_and_visualize])
    sys_msg = SystemMessage(content=CODE_SANDBOX_PROMPT)
    response = await llm.ainvoke([sys_msg] + state["messages"])
    return {"messages": [response], "active_agent": "code_sandbox"}

# ---------------------------------------------------------
# SUPERVISOR
# ---------------------------------------------------------

class RouterChoice(TypedDict):
    next_agent: Literal["researcher", "knowledge_vault", "document_generator", "code_sandbox", "FINISH"]
    reasoning: str

async def supervisor_agent(state: AgentState):
    """
    The Supervisor routes the task to the correct specialized worker.
    If the user's request is simple chat or all tasks are done, it responds directly (FINISH).
    """
    llm = get_llm(state["model_name"])
    
    # We use structured output to force the LLM to pick a route
    router = llm.with_structured_output(RouterChoice)
    
    sys_msg = SystemMessage(content=SUPERVISOR_PROMPT)
    
    # If the last message was a tool execution, we must synthesize the final answer
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage):
        # Synthesize final response — include sys_msg so the AI has its persona
        final_response = await llm.ainvoke([sys_msg] + state["messages"])
        return {"messages": [final_response], "active_agent": "supervisor"}
        
    choice = await router.ainvoke([sys_msg] + state["messages"])
    
    if choice["next_agent"] == "FINISH":
        # Just chat normally — include sys_msg for consistent AI persona
        final_response = await llm.ainvoke([sys_msg] + state["messages"])
        return {"messages": [final_response], "active_agent": "supervisor"}
    
    # Otherwise, return nothing to messages, just update active_agent so the router knows where to go
    return {"active_agent": choice["next_agent"]}

# ---------------------------------------------------------
# ROUTING LOGIC
# ---------------------------------------------------------

def supervisor_router(state: AgentState):
    agent = state.get("active_agent", "supervisor")
    if agent == "supervisor":
        return END
    return agent

def worker_router(state: AgentState):
    last_message = state["messages"][-1]
    # If the worker called a tool, route to the tool node
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    # Otherwise, the worker is done, go back to supervisor
    return "supervisor"

# ---------------------------------------------------------
# GRAPH CONSTRUCTION
# ---------------------------------------------------------

workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor_agent)
workflow.add_node("researcher", researcher_agent)
workflow.add_node("knowledge_vault", knowledge_vault_agent)
workflow.add_node("document_generator", document_generator_agent)
workflow.add_node("code_sandbox", code_sandbox_agent)

# One central Tool Node for all tools (since each agent is bound to only their specific tools)
all_tools = [tavily_search, search_uploaded_documents, generate_and_upload_document, execute_python_and_visualize]
workflow.add_node("tools", ToolNode(all_tools))

# Edges
workflow.add_edge(START, "supervisor")

# Supervisor decides who to call
workflow.add_conditional_edges("supervisor", supervisor_router, {
    "researcher": "researcher",
    "knowledge_vault": "knowledge_vault",
    "document_generator": "document_generator",
    "code_sandbox": "code_sandbox",
    END: END
})

# Workers decide to call tools or go back to supervisor
for worker in ["researcher", "knowledge_vault", "document_generator", "code_sandbox"]:
    workflow.add_conditional_edges(worker, worker_router, {
        "tools": "tools",
        "supervisor": "supervisor"
    })

# Tools always route back to the supervisor so it can synthesize
workflow.add_edge("tools", "supervisor")

# Compile graph
agent_executor = workflow.compile()
