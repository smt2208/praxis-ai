"""
agents/routing.py

CEO Router — fast-path pattern matching + LLM-based routing.
Extracted from orchestrator.py so routing logic lives in one place,
is independently testable, and keeps orchestrator.py lean.

Public API:
    resolve_route(query, history_text, doc_context, has_documents, has_images, image_context) -> RouteDecision
"""
import re
import logging
from typing import Literal, Optional

from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import DEFAULT_MODEL
from prompts.orchestrator_prompts import ROUTER_SYSTEM

logger = logging.getLogger(__name__)

RouteLabel = Literal["vision_agent", "knowledge_team", "research_team", "follow_up", "general"]
SecondaryLabel = Literal["general", "knowledge_team", "research_team"]


# ---------------------------------------------------------------------------
# Structured output schema — LLM must return exactly this
# ---------------------------------------------------------------------------

class RouteDecision(BaseModel):
    """
    The CEO must output exactly this schema — no free-form text.

    primary_route:  The main department to handle the query.
    secondary_route: An optional second department for hybrid cross-modal queries
                     (e.g., compare document with live web search).
    is_hybrid:      True only when both primary AND secondary must run in parallel.
    """
    primary_route: RouteLabel
    secondary_route: Optional[SecondaryLabel] = None
    is_hybrid: bool = False


# ---------------------------------------------------------------------------
# LLMs (module-level singletons — instantiated once at import time)
# ---------------------------------------------------------------------------

_ceo_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)
router_llm = _ceo_llm.with_structured_output(RouteDecision)   # exported for follow_up_llm use


# ---------------------------------------------------------------------------
# Fast-path patterns — skip the LLM entirely for obvious intents
# ---------------------------------------------------------------------------

_TRIVIAL_PATTERNS = re.compile(
    r"^(hi|hello|hey|yo|sup|thanks|thank you|thx|ok|okay|sure|"
    r"got it|cool|nice|great|good|bye|goodbye|see you|cheers|"
    r"good morning|good evening|good night|gm|gn)[\s!.,?]*$",
    re.IGNORECASE,
)

_FOLLOW_UP_PATTERNS = re.compile(
    r"^(make it |translate |convert |rewrite |rephrase |"
    r"shorten |expand |simplify |format |summarize this|"
    r"explain that|say that again|what do you mean|"
    r"can you clarify|more details|elaborate)",
    re.IGNORECASE,
)

_RESEARCH_PATTERNS = re.compile(
    r"(^research |do a deep dive |analyze .* literature|"
    r"search arxiv|search pubmed|write a .* report on |"
    r"comprehensive analysis of |investigate the )",
    re.IGNORECASE,
)


def _fast_route(query: str, has_history: bool, has_images: bool = False) -> RouteDecision | None:
    """
    Return a RouteDecision if intent is obvious from pattern matching / image presence alone,
    or None to fall through to the LLM router.

    Rules (in order):
      1. Images present                         → vision_agent (0 ms)
      2. Trivial greetings / pleasantries       → follow_up (0 ms)
      3. Explicit formatting / rephrase request → follow_up (only needs history)
      4. Explicit deep-research keywords        → research_team
      5. Anything else                          → None (let LLM decide)
    """
    if has_images:
        return RouteDecision(primary_route="vision_agent")

    stripped = query.strip()

    if _TRIVIAL_PATTERNS.match(stripped):
        return RouteDecision(primary_route="follow_up")

    if has_history and _FOLLOW_UP_PATTERNS.match(stripped):
        return RouteDecision(primary_route="follow_up")

    if _RESEARCH_PATTERNS.search(stripped):
        return RouteDecision(primary_route="research_team")

    return None


# ---------------------------------------------------------------------------
# Hard gate — Python-enforced, cannot be bypassed by prompt injection
# ---------------------------------------------------------------------------

def _apply_hard_gates(decision: RouteDecision, has_documents: bool, has_images: bool) -> RouteDecision:
    """
    Apply safety checks:
    - knowledge_team requires documents; redirect to general if not available.
    - vision_agent requires images; redirect to general if not present.
    - If hybrid secondary is knowledge_team but no documents → drop secondary.
    """
    primary = decision.primary_route
    secondary = decision.secondary_route

    if primary == "knowledge_team" and not has_documents:
        primary = "general"
        secondary = None
    elif primary == "vision_agent" and not has_images:
        primary = "general"
        secondary = None

    if secondary == "knowledge_team" and not has_documents:
        secondary = None

    is_hybrid = bool(secondary) and secondary != primary
    return RouteDecision(primary_route=primary, secondary_route=secondary if is_hybrid else None, is_hybrid=is_hybrid)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def resolve_route(
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
      1. Fast-path: image detection & regex pattern matching (0 ms, no API call)
      2. LLM routing: structured output call for ambiguous queries (~500 ms)
      3. Hard gates: knowledge_team/vision_agent only reachable when assets present
      4. Crash-proof fallback: route to 'general' if LLM call fails
    """
    # Step 1: Fast-path
    fast = _fast_route(query, has_history=bool(history_text), has_images=has_images)
    if fast:
        decision = _apply_hard_gates(fast, has_documents, has_images)
        logger.info("[Router] Fast-path: '%s' (images=%s) -> %s", query[:60], has_images, decision.primary_route)
        return decision

    # Step 2: LLM routing with crash-proof fallback
    try:
        context_block = "\n".join(filter(None, [doc_context, image_context]))
        routing_messages = [
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=(
                f"{context_block}\n\nConversation so far:\n{history_text}\n\nLatest user message: {query}"
                if history_text else
                f"{context_block}\n\nUser message: {query}"
            )),
        ]
        decision: RouteDecision = router_llm.invoke(routing_messages)
    except Exception as exc:
        # Step 4: Never let a routing failure crash the request
        logger.error("[Router] LLM routing failed, falling back to 'general': %s", exc)
        decision = RouteDecision(primary_route="general")

    # Step 3: Hard gate
    decision = _apply_hard_gates(decision, has_documents, has_images)
    logger.info(
        "[Router] Query: '%s' -> %s%s",
        query[:60],
        decision.primary_route,
        f" + {decision.secondary_route} (hybrid)" if decision.is_hybrid else "",
    )
    return decision
