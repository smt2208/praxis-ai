import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.api.routers import auth, chat, documents

from src.db.session import engine
from src.db.models import Base
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs on startup: Automatically create all tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # This runs on shutdown: Gracefully close DB connections
    await engine.dispose()

app = FastAPI(
    title="Multimodal Agentic Chatbot API",
    description="Fully online, agentic, multimodal chatbot backend.",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
# NOTE: allow_origins=["*"] with allow_credentials=True is rejected by browsers.
# List your frontend URL(s) here. For development, localhost is included.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(documents.router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Backend is running smoothly!"}

def main():
    """Start the FastAPI server."""
    print(f"""
╔════════════════════════════════════════════════════════════╗
║             Multimodal Agentic Chatbot v2.0               ║
║             Starting API Server...                        ║
╚════════════════════════════════════════════════════════════╝

🚀 Server: http://{settings.api_host}:{settings.api_port}
📚 API Docs: http://{settings.api_host}:{settings.api_port}/docs
""")
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
