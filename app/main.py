"""
main.py — FastAPI application entry point

Startup sequence (via lifespan):
  1. Load & validate settings
  2. Connect asyncpg pool → create / migrate tables
  3. Compile LangGraph orchestrator (at import time in orchestrator.py)
  4. Attach rate limiter
  5. App ready

Endpoints:
  POST   /api/v1/auth/register            → create account + return JWT
  POST   /api/v1/auth/login               → return JWT
  GET    /api/v1/auth/me                  → current user info (protected)

  GET    /api/v1/conversations            → list user's conversations (protected)
  POST   /api/v1/conversations            → create conversation (protected)
  GET    /api/v1/conversations/{id}/messages → fetch message history (protected)

  POST   /api/v1/chat                     → main chat endpoint (protected, rate-limited)
  POST   /api/v1/ingest                   → document ingestion pipeline
  GET    /health                          → DB + Qdrant health check
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from qdrant_client import QdrantClient

from app.config import get_settings
from app.database import (
    init_db_pool, get_history, save_message,
    create_conversation, get_conversations_by_user,
    mark_conversation_has_documents, get_conversation_has_documents,
)
from app.schemas import (
    ChatRequest, ChatResponse,
    ConversationCreateRequest, ConversationResponse,
    ConversationListItem, ConversationListResponse,
    MessageResponse, IngestRequest, IngestResponse,
    HealthResponse,
)
from app.auth.router import router as auth_router
from app.auth.dependencies import get_current_user
from app.middleware.rate_limit import limiter, rate_limit_handler
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

# Rate limiter — must be set before any route uses @limiter.limit()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth router (register, login, me)
app.include_router(auth_router)


# --- Shared pool dependency -------------------------------------------

async def get_pool(request: Request) -> asyncpg.Pool:
    """Inject the asyncpg pool from app.state into any endpoint."""
    return request.app.state.db_pool


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
        await asyncio.to_thread(client.get_collections)
        qdrant_status = "ok"
    except Exception as e:
        qdrant_status = f"error: {e}"

    overall = "healthy" if db_status == "ok" and qdrant_status == "ok" else "degraded"
    return HealthResponse(status=overall, database=db_status, qdrant=qdrant_status)


# --- Conversations (protected) -----------------------------------------

@app.get(
    "/api/v1/conversations",
    response_model=ConversationListResponse,
    tags=["Conversations"],
)
async def list_conversations(
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """Return all conversations belonging to the authenticated user."""
    rows = await get_conversations_by_user(pool, current_user["id"])
    items = [
        ConversationListItem(
            conversation_id=str(r["id"]),
            title=r["title"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]
    return ConversationListResponse(conversations=items)


@app.post(
    "/api/v1/conversations",
    response_model=ConversationResponse,
    status_code=201,
    tags=["Conversations"],
)
async def new_conversation(
    body: ConversationCreateRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """Create a new conversation thread for the authenticated user."""
    conv_id = await create_conversation(pool, current_user["id"], body.title)
    return ConversationResponse(conversation_id=conv_id)


@app.get(
    "/api/v1/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
    tags=["Conversations"],
)
async def get_messages(
    conversation_id: str,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """Fetch the message history for a conversation (must belong to the user)."""
    rows = await get_history(pool, conversation_id, limit=50)
    return [MessageResponse(role=r["role"], content=r["content"]) for r in rows]


# --- Chat (main endpoint — protected + rate-limited) ------------------

@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Chat"])
@limiter.limit("20/minute")            # 20 messages per minute per user
async def chat(
    request: Request,                  # required by slowapi
    body: ChatRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),
):
    """
    Main chat endpoint.
    - Reads user identity from JWT (not from the request body).
    - Fetches clean history from DB, runs the multi-agent graph, persists results.
    """
    # 1. Fetch conversation history + check if conversation has documents (one concurrent batch)
    history, has_documents = await asyncio.gather(
        get_history(pool, body.conversation_id, limit=20),
        get_conversation_has_documents(pool, body.conversation_id),
    )

    # Persist the user's turn first (never lost even if the graph fails)
    await save_message(pool, body.conversation_id, "user", body.message)

    # 2. Run the stateless multi-agent graph
    try:
        # Offload the synchronous LangGraph execution to a worker thread
        # This prevents the FastAPI async event loop from freezing while the LLM generates!
        result = await asyncio.to_thread(
            invoke_graph,
            query=body.message,
            history=history,
            user_id=current_user["id"],
            conversation_id=body.conversation_id,
            has_documents=has_documents,  # hard gate: blocks knowledge_team if False
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # 3. Persist the assistant reply after generation succeeds
    await save_message(pool, body.conversation_id, "assistant", result["answer"])

    return ChatResponse(
        conversation_id=body.conversation_id,
        answer=result["answer"],
        route_taken=result["route"],
    )


# --- Ingestion ---------------------------------------------------------

@app.post("/api/v1/ingest", response_model=IngestResponse, tags=["Ingestion"])
async def ingest(
    body: IngestRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(get_current_user),  # JWT required
):
    """
    Ingest a document from a URL into the authenticated user's private knowledge base.
    Documents are tagged with the conversation ID so retrieval is fully isolated per conversation.
    """
    try:
        count = await ingest_document(
            source_url=body.source_url,
            user_id=current_user["id"],
            conversation_id=body.conversation_id,
            collection_name=body.collection_name,
        )
        # Flip the conversation's has_documents flag so the CEO can route to knowledge_team
        await mark_conversation_has_documents(pool, body.conversation_id)
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
