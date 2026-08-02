"""
main.py — FastAPI application entry point

Startup sequence (via lifespan):
  1. Load & validate settings
  2. Connect asyncpg pool → create / migrate tables
  3. Compile LangGraph orchestrator (at import time in orchestrator.py)
  4. Attach rate limiter & middleware
  5. Include modular APIRouters
  6. App ready
"""
from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.db import init_db_pool
from app.auth.router import router as auth_router
from app.routers.health import router as health_router
from app.routers.conversations import router as conversations_router
from app.routers.chat import router as chat_router
from app.routers.ingest import router as ingest_router
from app.routers.memory import router as memory_router
from app.services.warmup import warmup_all_services
from app.middleware.rate_limit import limiter, rate_limit_handler

settings = get_settings()
logger = logging.getLogger(__name__)


# --- Lifespan ----------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # ── Startup ──────────────────────────────────────────────────────
    logger.info("[startup] Connecting to PostgreSQL...")
    app.state.db_pool = await init_db_pool(settings)
    logger.info("[startup] Database ready. Tables ensured.")

    logger.info("[startup] LangGraph orchestrator compiled.")

    # Pre-warm FastEmbed BM25 sparse model and Mem0 memory instance to eliminate first-query cold start latency
    await warmup_all_services()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("[shutdown] Closing database pool...")
    await app.state.db_pool.close()


# --- App ---------------------------------------------------------------

app = FastAPI(
    title="Praxis",
    description="Stateless Hierarchical Multi-Agent API",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiter — must be set before any route uses @limiter.limit()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)


# --- Global User-Friendly Exception Handlers ---------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all for any unhandled internal server error across all endpoints/modules.
    Logs the full exception traceback for developers, but returns a clean,
    user-friendly error message to the client (no technical codes or stack traces).
    """
    logger.exception("[Unhandled Error] Path: %s | Error: %s", request.url.path, str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred while processing your request. Please try again or contact support."},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Sanitize HTTP exceptions so users always see clean, professional messages."""
    detail = str(exc.detail) if exc.detail else "An error occurred."
    if "Traceback" in detail or "Error code:" in detail or "rate_limit_exceeded" in detail:
        logger.error("[HTTP Exception Sanitized] Path: %s | Raw Detail: %s", request.url.path, detail)
        detail = "The service encountered a temporary issue while processing your request. Please try again in a moment."

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Modular APIRouters
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(ingest_router)
app.include_router(memory_router)


# --- Dev runner --------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=True)
