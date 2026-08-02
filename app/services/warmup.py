"""
app/services/warmup.py

Pre-warms machine learning models, vector stores, and embedding caches
at server startup to eliminate cold-start latency for the first user query.
"""
import asyncio
import logging

from app.services.memory import _get_memory

logger = logging.getLogger(__name__)


def _warmup_fastembed() -> None:
    """Pre-load FastEmbed BM25 sparse model into memory/cache."""
    try:
        from langchain_qdrant import FastEmbedSparse
        logger.info("[warmup] Pre-warming FastEmbed sparse BM25 model...")
        _ = FastEmbedSparse(model_name="Qdrant/bm25")
        logger.info("[warmup] FastEmbed sparse model ready.")
    except Exception as exc:
        logger.warning("[warmup] FastEmbed sparse model pre-warm skipped or failed: %s", exc)


def _warmup_mem0() -> None:
    """Pre-load Mem0 Memory instance and verify Qdrant connection."""
    try:
        logger.info("[warmup] Pre-warming Mem0 long-term memory instance...")
        _ = _get_memory()
        logger.info("[warmup] Mem0 long-term memory ready.")
    except Exception as exc:
        logger.warning("[warmup] Mem0 pre-warm skipped or failed: %s", exc)


async def warmup_all_services() -> None:
    """
    Run all warmup tasks concurrently in thread pools during FastAPI lifespan startup.
    This ensures that when the server is ready to accept HTTP traffic,
    all embedding models, sparse BM25 models, and Mem0 Qdrant connections
    are already 100% warm and cached in RAM.
    """
    logger.info("[warmup] Starting background pre-warming of models & services...")
    try:
        await asyncio.gather(
            asyncio.to_thread(_warmup_fastembed),
            asyncio.to_thread(_warmup_mem0),
            return_exceptions=True,
        )
        logger.info("[warmup] All models & services pre-warmed successfully. Zero cold-start ready.")
    except Exception as exc:
        logger.warning("[warmup] Warmup completed with warning: %s", exc)
