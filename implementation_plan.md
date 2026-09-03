# Implementation Plan: Hybrid Adaptive Multi-Agent Architecture for Praxis AI

Upgrade Praxis AI from a strict single-route supervisor into a **Hybrid Adaptive Multi-Agent Architecture** featuring:
1. **Parallel Fan-Out / Fan-In (Map-Reduce Routing)**: Resolves the single-route bottleneck by allowing concurrent execution of document RAG, vision, and web search for cross-modal and comparative queries.
2. **Corrective RAG (CRAG) with Multi-Query Expansion**: Boosts retrieval recall across technical PDFs by generating alternative query perspectives and grading retrieved chunks before synthesis.
3. **Lightweight Quality Gate (Evaluator-Optimizer)**: Employs a low-latency check (`gpt-5.4-nano`) to verify groundedness and prompt completeness before finalizing answers.

---

## User Review Required

> [!IMPORTANT]
> **No Database or API Schema Breaking Changes**:
> The proposed architecture strictly preserves existing API contracts (`/api/v1/chat/stream`, `/api/v1/chat`, and WebSocket/SSE event shapes). The frontend receives the same event types (`agent_start`, `token`, `done`), but can now display multi-agent status updates (e.g. `agent: "knowledge_team + general"`).

> [!NOTE]
> **Model Budget & Latency Optimization**:
> - Single-route queries (chit-chat, simple web lookups, pure document queries) remain single-pass and ultra-fast.
> - Parallel execution runs via `asyncio.gather`, meaning a hybrid query (Docs + Web) completes in approximately the **same time** as a single web search, rather than sequentially doubling latency.
> - The Evaluator check runs on `FAST_MODEL` (`gpt-5.4-nano`) with a 2-second timeout and only triggers a 1-pass refinement when a hallucination or omission is detected.

---

## Open Questions

> [!TIP]
> **Synthesizer Streaming Preference**:
> When a query executes both Knowledge Team and General Agent in parallel, should the synthesizer begin streaming the combined answer as soon as both finish their research, or should tokens from the primary agent stream immediately while the secondary agent gathers supplementary facts? (Recommended: Parallel fetch $\to$ Unified synthesized stream for cohesive, non-fragmented answers).

---

## Proposed Changes

### Routing & Orchestration Layer

#### [MODIFY] [routing.py](file:///e:/Running-projects/praxis-ai/agents/routing.py)
- Update `RouteDecision` Pydantic model to support both primary and secondary routes:
  ```python
  class RouteDecision(BaseModel):
      primary_route: Literal["vision_agent", "knowledge_team", "research_team", "follow_up", "general"]
      secondary_route: Optional[Literal["general", "knowledge_team", "research_team"]] = None
      is_hybrid: bool = False
      synthesis_instructions: Optional[str] = None
  ```
- Update router prompt (`ROUTER_SYSTEM`) to identify queries that require cross-department intelligence:
  - Examples: *"Compare attached document with recent news"*, *"Explain this uploaded diagram and check if newer versions exist on the web"*.
- Preserve regex fast-paths (`_TRIVIAL_PATTERNS`, `_FOLLOW_UP_PATTERNS`) to ensure 0-cost routing for greetings and quick follow-ups.

#### [MODIFY] [orchestrator.py](file:///e:/Running-projects/praxis-ai/agents/orchestrator.py)
- Implement parallel fan-out in `astream_graph_events`:
  - If `is_hybrid` is `False`: Execute the standard single-department streaming pipeline.
  - If `is_hybrid` is `True`:
    1. Emit dual status event: `{"event": "agent_start", "data": {"agent": "hybrid", "message": "Searching documents and live web in parallel..."}}`.
    2. Concurrently execute both department subgraphs via `asyncio.gather()`.
    3. Feed both outputs to a lightweight `MultiAgentSynthesizer` that streams the unified answer.

---

### Corrective RAG (CRAG) Layer

#### [MODIFY] [knowledge_team.py](file:///e:/Running-projects/praxis-ai/agents/subgraphs/knowledge_team.py)
- **Multi-Query Expansion**:
  - Replace single-query reformulation with an async expander that outputs 2 complementary search queries (e.g. specific technical phrasing + conceptual keywords).
  - Execute Qdrant hybrid search across both perspectives, merging results via Reciprocal Rank Fusion (RRF) and deduplicating chunks by chunk ID.
- **Relevance Grading (CRAG Gate)**:
  - Fast chunk grading step (`aevaluate_doc_context`):
    - **Grade A (High relevance)**: Direct synthesis from document chunks.
    - **Grade B (Partial / Ambiguous)**: Automatically trigger real-time Tavily search and merge external context.
    - **Grade C (No relevance in document)**: Inform user transparently or fall back cleanly to web search instead of hallucinating.

---

### Quality Gate (Evaluator-Optimizer)

#### [NEW] [evaluator.py](file:///e:/Running-projects/praxis-ai/agents/evaluator.py)
- Implement `aevaluate_response(query: str, answer: str, context: str) -> EvaluationResult`:
  - Checks:
    1. *Groundedness*: Are all factual claims supported by context/chunks?
    2. *Completeness*: Did it address all aspects of the user prompt?
  - Returns `{"passed": bool, "feedback": str}`.
  - Placed as an optional post-check for heavy RAG and Research answers.

---

### Prompts & Synthesizers

#### [MODIFY] [orchestrator_prompts.py](file:///e:/Running-projects/praxis-ai/prompts/orchestrator_prompts.py)
- Add `MULTI_AGENT_SYNTHESIZER_SYSTEM`: Instructions on harmonizing document evidence with live web research without contradictory statements.
- Add `CEO_EVALUATOR_SYSTEM`: Rubric for groundedness and prompt completeness verification.

---

## Verification Plan

### Automated Tests
1. **Routing Verification**:
   - Test single-intent queries (*"Hello"*, *"Summarize this document"*, *"What is the stock price of Apple?"*).
   - Test hybrid queries (*"How does our attached Q3 revenue compare with recent market news?"*).
2. **CRAG Ingestion & Retrieval**:
   - Verify multi-query retrieval returns relevant chunks from dense + sparse index.
   - Verify fallback to Tavily when document does not contain the answer.
3. **Streaming & SSE Protocol**:
   - Verify `astream_graph_events` emits valid JSON SSE chunks without breaking client stream decoders.
   - Verify syntax compilation across all modules: `python -m compileall app/ agents/ prompts/`.

### Manual Verification
- **Test Case 1 (Single Path)**: Send a general query (*"Explain quantum computing in simple terms"*). Confirm response streams instantly from General Agent.
- **Test Case 2 (Hybrid Path)**: Upload a document (e.g. `Concept & BRD AEO_GEO.pdf`) and ask *"Compare the key requirements in this document with recent 2026 industry standards"*. Confirm both document retrieval and web search execute concurrently and yield a synthesized answer.
- **Test Case 3 (Document Only)**: Ask a specific question about an uploaded PDF. Confirm RAG retrieval answers cleanly with source attribution.
