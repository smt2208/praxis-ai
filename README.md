# Praxis AI 🧠

**Praxis AI** is a robust, stateless, hierarchical Multi-Agent API built for complex reasoning and enterprise-scale task execution. Instead of relying on a single monolithic prompt, Praxis AI operates like a digital corporation: a top-level **CEO Orchestrator** analyzes user requests and dynamically routes them to specialized AI sub-teams (e.g., Knowledge Team or Research Team) for precise, cost-effective, and hallucination-resistant responses.

## 🏗 Architecture

The system utilizes a fully stateless design via `langgraph`, meaning memory is persisted in a PostgreSQL database and injected per-request, enabling infinite horizontal scaling.

```mermaid
graph TD
    %% Visual Styles
    classDef client fill:#d4edda,stroke:#28a745,stroke-width:2px,color:#155724;
    classDef api fill:#cce5ff,stroke:#007bff,stroke-width:2px,color:#004085;
    classDef agent fill:#fff3cd,stroke:#ffc107,stroke-width:2px,color:#856404;
    classDef db fill:#e2e3e5,stroke:#383d41,stroke-width:2px,color:#383d41;

    %% Components
    User([👤 User Client]):::client
    API[⚡ FastAPI Backend]:::api
    DB[(🐘 RDS PostgreSQL)]:::db
    Qdrant[(💠 Qdrant Hybrid DB)]:::db
    Web((🌐 Web / ArXiv)):::db
    
    subgraph LangGraph [🤖 Autonomous Multi-Agent Swarm]
        CEO{🧠 CEO Orchestrator}:::agent
        Knowledge[📚 Knowledge Team]:::agent
        Research[🔬 Research Team]:::agent
        FollowUp[💬 Follow-up Agent]:::agent
    end

    %% Flow
    User -- 1. POST /chat --> API
    API <-- 2. Load & Save History --> DB
    
    API -- 3. Execute Graph --> CEO
    
    CEO -- "RAG/News" --> Knowledge
    CEO -- "Literature" --> Research
    CEO -- "Casual" --> FollowUp
    
    Knowledge -. 4a. Hybrid Search .-> Qdrant
    Research -. 4b. Iterative Search .-> Web
    
    Knowledge -- 5. Synthesize --> API
    Research -- 5. Report --> API
    FollowUp -- 5. Chat --> API
    
    API -- 6. JSON Response --> User
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
