"""
agents/subgraphs/vision_agent.py

Vision Agent — Multimodal Image Understanding Department.

Processes image inputs (base64 data URIs) using GPT-4o vision capabilities.
Handles visual Q&A, diagram analysis, OCR, code extraction from screenshots, etc.
"""
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langsmith import traceable

from app.config import DEFAULT_MODEL

logger = logging.getLogger(__name__)

VISION_SYSTEM = """You are Praxis Vision Agent, an expert AI specialized in computer vision, visual document analysis, OCR, diagram understanding, and visual problem solving.

Guidelines:
1. Provide accurate, detailed, and structured insights about the provided image(s).
2. If the user asks specific questions, address them directly based on visual evidence in the image(s).
3. If text, code, tables, or math formulas appear in the image, transcribe or explain them accurately using Markdown formatting.
4. If multiple images are provided, compare and contrast them when appropriate.
5. Be concise, clear, and direct. Avoid unnecessary fluff.
"""

_vision_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.2, max_tokens=2048)


def _prepare_vision_messages(query: str, images: list[str], history: list) -> list[BaseMessage]:
    """
    Construct multimodal message list containing text + base64 image_url content blocks.
    """
    recent_history = list(history[-6:]) if history else []

    # Build multimodal content list for the latest user message
    user_content = []
    
    text_prompt = query.strip() if query and query.strip() else "Please describe and analyze the provided image(s) in detail."
    user_content.append({"type": "text", "text": text_prompt})

    for img in images[:5]:  # Safety cap at 5 images max
        if isinstance(img, str) and img.strip():
            url_val = img.strip()
            # Ensure valid data URI prefix if raw base64 was passed
            if not url_val.startswith("data:") and not url_val.startswith("http"):
                url_val = f"data:image/png;base64,{url_val}"
            user_content.append({
                "type": "image_url",
                "image_url": {"url": url_val}
            })

    multimodal_user_msg = HumanMessage(content=user_content)
    return [SystemMessage(content=VISION_SYSTEM)] + recent_history + [multimodal_user_msg]


@traceable(name="Vision Agent Run", run_type="chain")
def run_vision_agent(query: str, images: list[str], history: list) -> str:
    """Synchronous invocation for vision analysis."""
    messages = _prepare_vision_messages(query, images, history)
    response = _vision_llm.invoke(messages)
    return response.content if isinstance(response.content, str) else str(response.content)


@traceable(name="Vision Agent Stream", run_type="chain")
async def astream_vision_agent(query: str, images: list[str], history: list):
    """Async generator yielding LLM token strings in real-time for SSE."""
    messages = _prepare_vision_messages(query, images, history)
    async for chunk in _vision_llm.astream(messages):
        content = chunk.content
        if isinstance(content, str) and content:
            yield content
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                    yield block["text"]
