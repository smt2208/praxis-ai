"""
agents/evaluator.py

Lightweight Quality Gate Evaluator.
Runs a fast structured-output check to verify that a generated answer is:
  1. Grounded — all claims are traceable to the provided context.
  2. Complete  — all aspects of the user's query are addressed.

Used as an optional post-step after heavy RAG and Research answers.
Runs on FAST_MODEL (gpt-5.4-nano) with a short timeout to avoid adding latency.
"""
import asyncio
import logging
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import FAST_MODEL
from prompts.orchestrator_prompts import CEO_EVALUATOR_SYSTEM

logger = logging.getLogger(__name__)

# Timeout (seconds) — if the check takes longer, we skip it and pass through
_EVAL_TIMEOUT = 4


class EvaluationResult(BaseModel):
    passed: bool
    feedback: str


_eval_llm = ChatOpenAI(model=FAST_MODEL, temperature=0).with_structured_output(EvaluationResult)


async def aevaluate_response(query: str, answer: str, context: str) -> EvaluationResult:
    """
    Async quality gate: checks groundedness and completeness of an answer.

    Returns EvaluationResult with passed=True if the answer is good,
    or passed=False with actionable feedback if it needs refinement.

    On any error or timeout, returns passed=True to avoid blocking the response.
    """
    if not answer or not context:
        return EvaluationResult(passed=True, feedback="")

    prompt = (
        f"USER QUERY:\n{query}\n\n"
        f"RETRIEVED CONTEXT (ground truth):\n{context[:6000]}\n\n"
        f"AI ANSWER TO EVALUATE:\n{answer[:3000]}"
    )

    try:
        result: EvaluationResult = await asyncio.wait_for(
            _eval_llm.ainvoke([
                SystemMessage(content=CEO_EVALUATOR_SYSTEM),
                HumanMessage(content=prompt),
            ]),
            timeout=_EVAL_TIMEOUT,
        )
        if not result.passed:
            logger.warning("[Evaluator] Quality gate failed: %s", result.feedback)
        return result
    except asyncio.TimeoutError:
        logger.info("[Evaluator] Timed out — skipping quality check.")
        return EvaluationResult(passed=True, feedback="")
    except Exception as exc:
        logger.error("[Evaluator] Error during evaluation: %s", exc)
        return EvaluationResult(passed=True, feedback="")
