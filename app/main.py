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
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import init_db_pool
from app.auth.router import router as auth_router
from app.routers.health import router as health_router
from app.routers.conversations import router as conversations_router
from app.routers.chat import router as chat_router
from app.routers.ingest import router as ingest_router
from app.middleware.rate_limit import limiter, rate_limit_handler

settings = get_settings()


# --- Lifespan ----------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # ── Startup ──────────────────────────────────────────────────────
    print("[startup] Connecting to PostgreSQL...")
    app.state.db_pool = await init_db_pool(settings)
    print("[startup] Database ready. Tables ensured.")

    print("[startup] LangGraph orchestrator compiled.")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    print("[shutdown] Closing database pool...")
    await app.state.db_pool.close()


# --- App ---------------------------------------------------------------

app = FastAPI(
    title="Praxis AI",
    description="Stateless Hierarchical Multi-Agent API",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiter — must be set before any route uses @limiter.limit()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

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


# --- Dev runner --------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=True)
