# Praxis AI 🧠

**Praxis AI** is a robust, stateless, hierarchical Multi-Agent API built for complex reasoning and enterprise-scale task execution. Instead of relying on a single monolithic prompt, Praxis AI operates like a digital corporation: a top-level **CEO Orchestrator** analyzes user requests and dynamically routes them to specialized AI sub-teams (e.g., Knowledge Team or Research Team) for precise, cost-effective, and hallucination-resistant responses.

## 🏗 Architecture

The system utilizes a fully stateless design via `langgraph`, meaning memory is persisted in a PostgreSQL database and injected per-request, enabling infinite horizontal scaling.

```mermaid
graph TD
    %% Entities
    User([User Client])
    DB[(AWS RDS PostgreSQL)]
    Qdrant[(Qdrant Hybrid Vector Store)]
    Web((Internet / APIs))

    %% Core App
    subgraph FastAPI Application
        API[API Endpoints]
    end

    %% CEO Routing
    subgraph Multi-Agent Swarm (LangGraph)
        CEO{CEO Orchestrator}
        
        %% Department A
        subgraph Department A: Knowledge Team
            RAG[RAG Agent]
            WebExp[Web Expert]
            Synth[Synthesizer]
        end
        
        %% Department B
        subgraph Department B: Deep Research Team
            Plan[Planner]
            SearchLoop[Researcher Loop]
            Report[Reporter]
        end
        
        %% Department C
        FollowUp[Follow-Up Agent]
    end

    %% Flow
    User --> |POST /api/v1/chat| API
    API --> |Fetch History| DB
    API --> |Invoke Graph| CEO
    
    %% Routing
    CEO --> |RAG / Facts| RAG
    CEO --> |Academic / Deep Dive| Plan
    CEO --> |Casual Chat| FollowUp
    
    %% Knowledge Flow
    RAG --> |Query| Qdrant
    RAG --> WebExp
    WebExp --> |Tavily API| Web
    WebExp --> Synth
    
    %% Research Flow
    Plan --> SearchLoop
    SearchLoop -.-> |ArXiv + Tavily| Web
    SearchLoop --> |Max Iters| Report
    
    %% Output
    Synth --> |Answer| API
    Report --> |Report| API
    FollowUp --> |Answer| API
    
    API --> |Save Messages| DB
    API --> |Response| User
```

## ✨ Key Features

- **Stateless Execution:** State is maintained via `asyncpg` connected to AWS RDS, avoiding memory bloat and enabling stateless horizontal scaling.
- **Hierarchical Swarm:** Uses `langgraph` to isolate state within sub-teams (Knowledge vs. Research), preventing context pollution.
- **Hybrid Retrieval:** Qdrant vector store uses both dense (`text-embedding-3-small`) and sparse (`FastEmbedSparse BM25`) embeddings for maximum accuracy.
- **Smart Ingestion Pipeline:** Document ingestion powered by `LlamaParse`, pulling data directly from URLs, chunking it, and upserting into the knowledge base.
- **Safe Academic Research:** Dedicated arXiv tool wrapper (`arxiv==2.4.1`) combined with a multi-loop research agent writes extensive, cited literature reviews.

## 📂 Modular Project Structure

```text
praxis-ai/
├── app/
│   ├── main.py             # FastAPI entry point & routers
│   ├── database.py         # PostgreSQL connection & helpers
│   ├── schemas.py          # Pydantic validation models
│   └── config.py           # Environment variables (pydantic-settings)
├── agents/
│   ├── orchestrator.py     # CEO langgraph routing logic
│   ├── tools.py            # LangChain tool definitions (Tavily, arXiv, Qdrant)
│   └── subgraphs/
│       ├── knowledge_team.py
│       └── research_team.py
├── prompts/
│   ├── orchestrator_prompts.py
│   ├── knowledge_prompts.py
│   └── research_prompts.py
├── scripts/
│   └── ingestion.py        # Standalone LlamaParse + Qdrant ingester
├── .env                    # Secrets (OpenAI, Qdrant, RDS, etc.)
└── requirements.txt
```

## 🚀 Setup and Installation

### 1. Prerequisites
- Python 3.10+ (or Conda)
- AWS RDS (PostgreSQL) or local Postgres
- Qdrant Cloud or local Docker instance
- API Keys: OpenAI, Tavily, LlamaCloud

### 2. Install Dependencies
```bash
conda create -n mgpt python=3.13
conda activate mgpt
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
LLAMA_CLOUD_API_KEY=llx-...

POSTGRES_HOST=your-rds-endpoint.amazonaws.com
POSTGRES_PORT=5432
POSTGRES_USER=praxis
POSTGRES_PASSWORD="your_password_in_quotes_if_special_chars_present"
POSTGRES_DB=postgres

QDRANT_URL=https://your-cluster.qdrant.tech
QDRANT_API_KEY=your_key
QDRANT_COLLECTION_NAME=collection
```

### 4. Run the API Server
```bash
python -m app.main
```
*(The server will start on `http://0.0.0.0:8000`. Database tables are created automatically on startup).*

## 📖 API Usage

**1. Create a User**
```bash
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

**2. Create a Conversation**
```bash
curl -X POST http://localhost:8000/api/v1/conversations \
  -H "Content-Type: application/json" \
  -d '{"user_id": "<uuid>", "title": "First Session"}'
```

**3. Chat!**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "<uuid>",
    "user_id": "<uuid>",
    "message": "Do a thorough research on the impact of attention mechanisms in NLP"
  }'
```
*(The CEO will automatically route this to the `research_team`, which will perform loops of web and academic searches before returning a comprehensive markdown report).*
