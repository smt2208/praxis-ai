"""
main.py — FastAPI application entry point

Startup sequence (via lifespan):
  1. Load & validate settings
  2. Connect asyncpg pool → create tables if not exist
  3. Compile LangGraph orchestrator
  4. App ready

Endpoints:
  POST   /api/v1/users               → register a user
  POST   /api/v1/conversations        → create a conversation
  GET    /api/v1/conversations/{id}/messages → fetch history
  POST   /api/v1/chat                → main chat endpoint
  POST   /api/v1/ingest              → document ingestion pipeline
  GET    /health                     → DB + Qdrant health check
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient

from app.config import get_settings
from app.database import init_db_pool, get_history, save_message, create_conversation, create_user
from app.schemas import (
    ChatRequest, ChatResponse,
    ConversationCreateRequest, ConversationResponse,
    UserCreateRequest, UserResponse,
    MessageResponse, IngestRequest, IngestResponse,
    HealthResponse,
)
from agents.orchestrator import invoke_graph
from scripts.ingestion import ingest_document

settings = get_settings()


# --- Lifespan ----------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # ── Startup ──────────────────────────────────────────────────────
    print("[startup] Connecting to PostgreSQL...")
    app.state.db_pool = await init_db_pool(settings)
    print("[startup] Database ready. Tables ensured.")

    print("[startup] LangGraph orchestrator compiled.")
    # (graph is compiled at import time in orchestrator.py)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Dependency --------------------------------------------------------

async def get_pool() -> asyncpg.Pool:
    return app.state.db_pool


# --- Health ------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check(pool: asyncpg.Pool = Depends(get_pool)):
    # Check DB
    try:
        await pool.fetchval("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    # Check Qdrant
    try:
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        client.get_collections()
        qdrant_status = "ok"
    except Exception as e:
        qdrant_status = f"error: {e}"

    overall = "healthy" if db_status == "ok" and qdrant_status == "ok" else "degraded"
    return HealthResponse(status=overall, database=db_status, qdrant=qdrant_status)


# --- Users -------------------------------------------------------------

@app.post("/api/v1/users", response_model=UserResponse, tags=["Users"])
async def register_user(body: UserCreateRequest, pool: asyncpg.Pool = Depends(get_pool)):
    user_id = await create_user(pool, body.email)
    return UserResponse(user_id=user_id, email=body.email)


# --- Conversations -----------------------------------------------------

@app.post("/api/v1/conversations", response_model=ConversationResponse, tags=["Conversations"])
async def new_conversation(body: ConversationCreateRequest, pool: asyncpg.Pool = Depends(get_pool)):
    conv_id = await create_conversation(pool, body.user_id, body.title)
    return ConversationResponse(conversation_id=conv_id)


@app.get(
    "/api/v1/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
    tags=["Conversations"],
)
async def get_messages(conversation_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    rows = await get_history(pool, conversation_id, limit=50)
    return [MessageResponse(role=r["role"], content=r["content"]) for r in rows]


# --- Chat (main endpoint) ----------------------------------------------

@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(body: ChatRequest, pool: asyncpg.Pool = Depends(get_pool)):
    # 1. Fetch clean conversation history from DB
    history = await get_history(pool, body.conversation_id, limit=20)

    # 2. Run the stateless multi-agent graph
    try:
        result = invoke_graph(query=body.message, history=history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # 3. Persist user message + assistant reply
    await save_message(pool, body.conversation_id, "user", body.message)
    await save_message(pool, body.conversation_id, "assistant", result["answer"])

    return ChatResponse(
        conversation_id=body.conversation_id,
        answer=result["answer"],
        route_taken=result["route"],
    )


# --- Ingestion ---------------------------------------------------------

@app.post("/api/v1/ingest", response_model=IngestResponse, tags=["Ingestion"])
async def ingest(body: IngestRequest):
    """
    Ingest a document from a URL (S3 presigned URL, public URL, etc.).
    Parses with LlamaParse, chunks, embeds, and stores in Qdrant.
    """
    try:
        count = await ingest_document(
            source_url=body.source_url,
            collection_name=body.collection_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")

    return IngestResponse(
        message="Document ingested successfully.",
        documents_stored=count,
    )


# --- Dev runner --------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=True)
