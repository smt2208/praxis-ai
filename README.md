# Multimodal Agentic Chatbot

> A next-generation, fully autonomous, multimodal AI assistant backend. Powered by LangGraph, FastAPI, and Qdrant, featuring real-time SSE streaming, hybrid vector search, and dynamic tool usage (Agentic RAG, Web Search, and Document Generation).

---

## 🏗 Architecture

The backend is engineered for high-performance, asynchronous, multi-tenant production environments.

```mermaid
graph TD
    Client[Next.js Frontend] -->|JWT Auth / HTTP / SSE| FastAPI[FastAPI Backend]
    
    subgraph Core Services
        FastAPI -->|PostgreSQL (AsyncPG)| DB[(PostgreSQL)]
        FastAPI -->|SSE Stream| Client
    end

    subgraph Agentic Brain (LangGraph)
        FastAPI -->|Invoke| LangGraph[LangGraph State Machine]
        LangGraph -->|LLM| OpenAI_Gemini[OpenAI / Gemini]
    end

    subgraph Autonomous Tools
        LangGraph -->|Tool: Search Web| Tavily[Tavily Search API]
        LangGraph -->|Tool: Search Documents| Qdrant[(Qdrant Vector DB)]
        LangGraph -->|Tool: Generate PDF| S3[(AWS S3)]
    end

    subgraph Document Ingestion Pipeline
        FastAPI -->|Upload| LlamaCloud[LlamaCloud Parser]
        LlamaCloud -->|Extract Markdown| LangChain[LangChain Chunker]
        LangChain -->|Hybrid Vector| Qdrant
    end
```

---

## ✨ Features

### 🧠 Agentic RAG
Powered by **LangGraph**, the LLM operates as an autonomous agent. Instead of blindly answering, it analyzes the user's prompt and decides which tools to invoke, parsing the results dynamically before answering.

### 📚 Hybrid Vector Search
Integrated with **Qdrant**, the backend uses true Hybrid Search (Dense Vectors + BM25 Sparse Vectors) to find exact-match keywords and semantically similar concepts across user-uploaded documents.

### 📄 Multimodal Document Understanding
The platform relies on the bleeding-edge **LlamaCloud SDK** to ingest complex PDFs, DOCX, and PPTX files, perfectly preserving tables, layouts, and structures as LLM-readable Markdown.

### ⚡ Real-Time SSE Streaming
No more waiting 10 seconds for a response. The backend leverages `astream_events` to pipe **Server-Sent Events (SSE)** directly to the client. The frontend receives millisecond-level updates on what the AI is doing:
- `{"type": "tool_start", "tool": "search_uploaded_documents"}`
- `{"type": "token", "content": "H"}`

### 🏭 Document Generation & AWS S3
The LLM has the autonomous ability to generate comprehensive reports (PDFs, TXT, CSV) on the fly, upload them directly to a secure **AWS S3** bucket, and return a 1-hour expiring Pre-Signed Download URL to the user.

### 🔒 Enterprise Security
- **JWT Auth**: Full native `bcrypt` password hashing and JWT token generation.
- **Tenant Isolation**: Every document vector in Qdrant and every message in PostgreSQL is strictly scoped to `user_id` and `conversation_id`, guaranteeing zero cross-tenant data leakage.

---

## 🛠 Tech Stack

| Component | Technology |
|---|---|
| **Backend Framework** | FastAPI `[standard]` (Fully Asynchronous) |
| **Orchestration** | LangGraph + LangChain 1.x |
| **Database (Relational)** | PostgreSQL (via Async SQLAlchemy & asyncpg) |
| **Database (Vector)** | Qdrant (via `langchain-qdrant`) |
| **Cloud Storage** | AWS S3 (via `boto3` & `aioboto3`) |
| **Document Parser** | LlamaCloud (`AsyncLlamaCloud`) |
| **Web Search** | Tavily |
| **Security** | native `bcrypt` + `python-jose` |

---

## 🚀 Setup & Installation

### 1. Requirements
- Python 3.10+
- PostgreSQL instance (Local or AWS RDS)
- Qdrant instance (Local Docker or Qdrant Cloud)
- AWS S3 Bucket + IAM Credentials

### 2. Environment Variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### 3. Installation
Install the required packages using pip:
```bash
pip install -r requirements.txt
```

### 4. Run the Server
Start the fully asynchronous FastAPI server. The database tables will be auto-generated on startup.
```bash
uvicorn main:app --reload
```

---

## 📁 API Flow

1. **`POST /api/auth/register`** — Create an account.
2. **`POST /api/auth/login`** — Get your JWT Bearer Token.
3. **`POST /api/chat/conversations`** — Initialize a new chat room.
4. **`POST /api/documents/upload/{conversation_id}`** — Upload a PDF to LlamaCloud & Qdrant.
5. **`POST /api/chat/conversations/{conversation_id}/messages`** — Send a message (`stream=true`), trigger the LangGraph agent, and watch the SSE stream fly!

---
*Built with LangChain · LangGraph · FastAPI · Qdrant · PostgreSQL · AWS S3*


#check for cicd