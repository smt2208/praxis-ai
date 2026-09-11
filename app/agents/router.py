"""
app/agents/router.py

CEO Router — fast-path pattern matching + LLM-based routing.
Extracted from orchestrator.py so routing logic lives in one place,
is independently testable, and keeps orchestrator.py lean.

Public API:
    resolve_route(query, history_text, doc_context, has_documents, has_images, image_context) -> RouteDecision
"""
import re
import logging
from typing import Literal

from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import DEFAULT_MODEL
from app.agents.prompts.orchestrator import ROUTER_SYSTEM

logger = logging.getLogger(__name__)

RouteLabel = Literal["vision_agent", "knowledge_team", "research_team", "follow_up", "general"]


# ---------------------------------------------------------------------------
# Structured output schema — LLM must return exactly this
# ---------------------------------------------------------------------------

class RouteDecision(BaseModel):
    """
    The CEO must output exactly this schema — no free-form text.

    primary_route: The main department to handle the query.
    """
    primary_route: RouteLabel


# ---------------------------------------------------------------------------
# LLMs (module-level singletons — instantiated once at import time)
# ---------------------------------------------------------------------------

_ceo_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)
router_llm = _ceo_llm.with_structured_output(RouteDecision)


# ---------------------------------------------------------------------------
# Fast-path patterns — skip the LLM entirely for obvious intents
# ---------------------------------------------------------------------------

_TRIVIAL = re.compile(
    r"^(hi|hello|hey|yo|sup|thanks|thank you|thx|ok|okay|sure|"
    r"got it|cool|nice|great|good|bye|goodbye|see you|cheers|"
    r"good morning|good evening|good night|gm|gn)[\s!.,?]*$",
    re.IGNORECASE,
)

_FOLLOW_UP = re.compile(
    r"^(make it |translate |convert |rewrite |rephrase |"
    r"shorten |expand |simplify |format |summarize this|"
    r"explain that|say that again|what do you mean|"
    r"can you clarify|more details|elaborate)",
    re.IGNORECASE,
)

_RESEARCH = re.compile(
    r"(^research |do a deep dive |analyze .* literature|"
    r"search arxiv|search pubmed|write a .* report on |"
    r"comprehensive analysis of |investigate the )",
    re.IGNORECASE,
)


def _fast_route(query: str, *, has_history: bool, has_images: bool, has_documents: bool) -> RouteDecision | None:
    """
    Return a RouteDecision for obvious intents (0 ms, no LLM call), or None to
    fall through to the LLM router.

    Order:
      1. Images attached → vision_agent (with document context if documents present)
      2. Greetings       → follow_up
      3. Rephrase        → follow_up (needs history)
      4. Research        → research_team
      5. Else            → None (LLM decides)
    """
    if has_images:
        return RouteDecision(primary_route="vision_agent")

    q = query.strip()

    if _TRIVIAL.match(q):
        return RouteDecision(primary_route="follow_up")

    if has_history and _FOLLOW_UP.match(q):
        return RouteDecision(primary_route="follow_up")

    if _RESEARCH.search(q):
        return RouteDecision(primary_route="research_team")

    return None


# ---------------------------------------------------------------------------
# Hard gate — Python-enforced, cannot be bypassed by prompt injection
# ---------------------------------------------------------------------------

# Routes that require a specific asset to be present
_ASSET_GATES = {
    "knowledge_team": "has_documents",
    "vision_agent": "has_images",
}


def _apply_hard_gates(decision: RouteDecision, has_documents: bool, has_images: bool) -> RouteDecision:
    """
    Enforce resource requirements:
    - knowledge_team needs documents, vision_agent needs images.
    - If the primary route's asset is missing → redirect to general.
    """
    assets = {"has_documents": has_documents, "has_images": has_images}
    primary = decision.primary_route

    # Gate the primary route
    required = _ASSET_GATES.get(primary)
    if required and not assets[required]:
        primary = "general"

    return RouteDecision(primary_route=primary)


# ---------------------------------------------------------------------------
# LLM routing message builder
# ---------------------------------------------------------------------------

def _build_routing_prompt(query: str, history_text: str, context_block: str) -> list:
    """Build the message list for the LLM router call."""
    if history_text:
        user_content = (
            f"{context_block}\n\n"
            f"Conversation so far:\n{history_text}\n\n"
            f"Latest user message: {query}"
        )
    else:
        user_content = f"{context_block}\n\nUser message: {query}"

    return [
        SystemMessage(content=ROUTER_SYSTEM),
        HumanMessage(content=user_content),
    ]


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

async def resolve_route(
    query: str,
    history_text: str,
    doc_context: str,
    has_documents: bool,
    has_images: bool = False,
    image_context: str = "",
) -> RouteDecision:
    """
    Determine the correct agent route for a query.

    Strategy (in order):
      1. Fast-path — regex / asset detection (0 ms, no API call)
      2. LLM routing — structured output call (~500 ms)
      3. Hard gates — knowledge_team / vision_agent only reachable when assets present
      4. Crash-proof fallback — route to 'general' if LLM call fails
    """
    # 1. Fast-path
    fast = _fast_route(query, has_history=bool(history_text), has_images=has_images, has_documents=has_documents)
    if fast:
        decision = _apply_hard_gates(fast, has_documents, has_images)
        logger.info("[Router] Fast-path: '%s' -> %s", query[:60], decision.primary_route)
        return decision

    # 2. LLM routing
    try:
        context_block = "\n".join(filter(None, [doc_context, image_context]))
        messages = _build_routing_prompt(query, history_text, context_block)
        raw_decision = await router_llm.ainvoke(messages)
        if isinstance(raw_decision, RouteDecision):
            decision = raw_decision
        elif isinstance(raw_decision, dict):
            decision = RouteDecision(**raw_decision)
        else:
            decision = RouteDecision(primary_route="general")
    except Exception as exc:
        logger.error("[Router] LLM routing failed, falling back to 'general': %s", exc)
        decision = RouteDecision(primary_route="general")

    # 3. Hard gates
    decision = _apply_hard_gates(decision, has_documents, has_images)
    logger.info("[Router] '%s' -> %s", query[:60], decision.primary_route)
    return decision
