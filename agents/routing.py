"""
agents/routing.py

CEO Router — fast-path pattern matching + LLM-based routing.
Extracted from orchestrator.py so routing logic lives in one place,
is independently testable, and keeps orchestrator.py lean.

Public API:
    resolve_route(query, history_text, doc_context, has_documents) -> str
"""
import re
import logging
from typing import Literal

from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import DEFAULT_MODEL
from prompts.orchestrator_prompts import ROUTER_SYSTEM

logger = logging.getLogger(__name__)

RouteLabel = Literal["knowledge_team", "research_team", "follow_up", "general"]


# ---------------------------------------------------------------------------
# Structured output schema — LLM must return exactly this
# ---------------------------------------------------------------------------

class RouteDecision(BaseModel):
    """The CEO must output exactly this schema — no free-form text."""
    route: RouteLabel


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


def _fast_route(query: str, has_history: bool) -> RouteLabel | None:
    """
    Return a route label if intent is obvious from pattern matching alone,
    or None to fall through to the LLM router.

    Rules (in order):
      1. Trivial greetings / pleasantries       → follow_up  (0 ms)
      2. Explicit formatting / rephrase request → follow_up  (only needs history)
      3. Explicit deep-research keywords        → research_team
      4. Anything else                          → None  (let LLM decide)
    """
    stripped = query.strip()

    if _TRIVIAL_PATTERNS.match(stripped):
        return "follow_up"

    if has_history and _FOLLOW_UP_PATTERNS.match(stripped):
        return "follow_up"

    if _RESEARCH_PATTERNS.search(stripped):
        return "research_team"

    return None


# ---------------------------------------------------------------------------
# Hard gate — Python-enforced, cannot be bypassed by prompt injection
# ---------------------------------------------------------------------------

def _apply_hard_gates(route: RouteLabel, has_documents: bool) -> RouteLabel:
    """knowledge_team requires documents; redirect to general if not available."""
    if route == "knowledge_team" and not has_documents:
        return "general"
    return route


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def resolve_route(
    query: str,
    history_text: str,
    doc_context: str,
    has_documents: bool,
) -> RouteLabel:
    """
    Determine the correct agent route for a query.

    Strategy (in order):
      1. Fast-path: regex pattern matching (0 ms, no API call)
      2. LLM routing: structured output call for ambiguous queries (~500 ms)
      3. Hard gates: knowledge_team only reachable when documents are present
      4. Crash-proof fallback: route to 'general' if LLM call fails
    """
    # Step 1: Fast-path
    fast = _fast_route(query, has_history=bool(history_text))
    if fast:
        route = _apply_hard_gates(fast, has_documents)
        logger.info("[Router] Fast-path: '%s' -> %s", query[:60], route)
        return route

    # Step 2: LLM routing with crash-proof fallback
    try:
        routing_messages = [
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=(
                f"{doc_context}\n\nConversation so far:\n{history_text}\n\nLatest user message: {query}"
                if history_text else
                f"{doc_context}\n\nUser message: {query}"
            )),
        ]
        decision: RouteDecision = router_llm.invoke(routing_messages)
        route = decision.route
    except Exception as exc:
        # Step 4: Never let a routing failure crash the request
        logger.error("[Router] LLM routing failed, falling back to 'general': %s", exc)
        route = "general"

    # Step 3: Hard gate
    route = _apply_hard_gates(route, has_documents)
    logger.info("[Router] Query: '%s' -> %s", query[:60], route)
    return route
