"""
app/agents/teams/vision.py

Vision Agent — Multimodal Image Understanding Department.
Processes image inputs (base64 data URIs) using vision capabilities.
Handles visual Q&A, diagram analysis, OCR, code extraction from screenshots, etc.
"""
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langsmith import traceable

from app.config import DEFAULT_MODEL
from app.agents.prompts.vision import VISION_SYSTEM

logger = logging.getLogger(__name__)

_vision_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.2, max_tokens=2048)


def _prepare_vision_messages(query: str, images: list[str], history: list) -> list[BaseMessage]:
    """
    Construct multimodal message list containing text + base64 image_url content blocks.
    """
    recent_history = list(history[-6:]) if history else []

    user_content = []
    text_prompt = query.strip() if query and query.strip() else "Please describe and analyze the provided image(s) in detail."
    user_content.append({"type": "text", "text": text_prompt})

    for img in images[:5]:  # Safety cap at 5 images max
        if isinstance(img, str) and img.strip():
            url_val = img.strip()
            if not url_val.startswith("data:") and not url_val.startswith("http"):
                url_val = f"data:image/png;base64,{url_val}"
            user_content.append({
                "type": "image_url",
                "image_url": {"url": url_val}
            })

    multimodal_user_msg = HumanMessage(content=user_content)
    return [SystemMessage(content=VISION_SYSTEM)] + recent_history + [multimodal_user_msg]


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

