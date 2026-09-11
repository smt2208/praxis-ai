"""
app/agents/teams/vision.py

Vision Agent — Multimodal Image Understanding Department.
Processes image inputs (base64 data URIs or S3 URLs) using vision capabilities.
Handles visual Q&A, diagram analysis, OCR, code extraction from screenshots, etc.
Built as a compiled LangGraph multimodal subgraph:
  [START] -> [generate] -> [END]
"""
import logging
from typing import Any, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from app.agents.prompts.vision import VISION_SYSTEM
from app.config import DEFAULT_MODEL

logger = logging.getLogger(__name__)

_vision_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.2)


# ---------------------------------------------------------------------------
# Subgraph State Definition
# ---------------------------------------------------------------------------

class VisionState(TypedDict):
    query: str
    images: list[str]
    history: list
    doc_context: str
    messages: list[BaseMessage]
    final_answer: str


def _prepare_vision_messages(query: str, images: list[str], history: list, doc_context: str = "") -> list[BaseMessage]:
    """
    Construct multimodal message list containing text + base64 image_url content blocks.
    When doc_context is provided, it is injected into the system prompt so the vision
    agent can cross-reference images with uploaded documents.
    """
    recent_history = list(history[-10:]) if history else []

    # Build system prompt — inject doc context if available
    system_text = VISION_SYSTEM
    if doc_context:
        system_text += (
            "\n\n--- DOCUMENT CONTEXT ---\n"
            "The user has uploaded documents in this conversation. "
            "Use the following document excerpts to cross-reference with the image(s) when relevant:\n\n"
            f"{doc_context}"
        )

    user_content: list[str | dict[Any, Any]] = []
    text_prompt = query.strip() if query and query.strip() else "Please describe and analyze the provided image(s) in detail."
    user_content.append({"type": "text", "text": text_prompt})

    for img in images[:5]:  # Safety cap at 5 images max
        if isinstance(img, str) and img.strip():
            url_val = img.strip()
            if not url_val.startswith("data:") and not url_val.startswith("http"):
                url_val = f"data:image/png;base64,{url_val}"
            user_content.append({
                "type": "image_url",
                "image_url": {"url": url_val},
            })

    multimodal_user_msg = HumanMessage(content=user_content)
    return [SystemMessage(content=system_text)] + recent_history + [multimodal_user_msg]


# ---------------------------------------------------------------------------
# LangGraph Subgraph Nodes
# ---------------------------------------------------------------------------

@traceable(name="Vision Generate Node", run_type="chain")
async def generate_node(state: VisionState) -> dict:
    """Generate multimodal analysis response."""
    messages = _prepare_vision_messages(
        state["query"],
        state.get("images", []),
        state.get("history", []),
        state.get("doc_context", ""),
    )
    response = await _vision_llm.ainvoke(messages)
    content = response.content if isinstance(response.content, str) else str(response.content)
    return {"messages": messages, "final_answer": content}


# ---------------------------------------------------------------------------
# Graph Assembly & Compilation
# ---------------------------------------------------------------------------

def _build_vision_graph():
    """Compile the Vision Agent subgraph."""
    builder = StateGraph(VisionState)
    builder.add_node("generate", generate_node)
    builder.add_edge(START, "generate")
    builder.add_edge("generate", END)
    return builder.compile()


_vision_graph = _build_vision_graph()


# ---------------------------------------------------------------------------
# Public Streaming Execution API
# ---------------------------------------------------------------------------

@traceable(name="Vision Agent Stream", run_type="chain")
async def astream_vision_agent(query: str, images: list[str], history: list, doc_context: str = ""):
    """
    Async generator yielding LLM token strings in real-time for SSE.

    Args:
        doc_context: Optional pre-fetched document context for cross-modal queries.
    """
    initial_state: VisionState = {
        "query": query,
        "images": images,
        "history": history,
        "doc_context": doc_context,
        "messages": [],
        "final_answer": "",
    }
    tokens_streamed = False

    async for mode, payload in _vision_graph.astream(
        initial_state,
        stream_mode=["messages", "updates"],
    ):
        if mode == "messages":
            chunk, metadata = payload
            if metadata.get("langgraph_node") == "generate":
                content = chunk.content
                if isinstance(content, str) and content:
                    tokens_streamed = True
                    yield content
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                            tokens_streamed = True
                            yield block["text"]
        elif mode == "updates":
            update = payload.get("generate", {})
            if not tokens_streamed and update.get("final_answer"):
                yield update["final_answer"]
