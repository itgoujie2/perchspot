# Semantic Search Knowledge Store — Implementation Plan

## Overview

Add a hybrid semantic search knowledge store (KNN + BM25) to the housing analysis platform. This enables ingesting categorized knowledge from `.md` files and retrieving relevant context to augment LLM analysis.

**Stack:**
- **Qdrant** — vector database (new Docker service)
- **Qwen3-Embedding-0.6B** — dense embeddings (1024-dim, via sentence-transformers)
- **FastEmbed Qdrant/bm25** — sparse BM25 vectors (ONNX-based, lightweight)
- **Reciprocal Rank Fusion (RRF)** — combines dense + sparse search results

---

## Phase 1: Infrastructure

### 1a. Add Qdrant to Docker Compose
**File:** `docker-compose.yml`
- Add `qdrant` service using `qdrant/qdrant:latest` image
- Port `6333:6333` (HTTP API) and `6334:6334` (gRPC)
- Named volume `qdrant_data:/qdrant/storage`
- Healthcheck: `curl -f http://localhost:6333/healthz`
- Add `qdrant` to backend's `depends_on`
- Add `QDRANT_URL: http://qdrant:6333` env var to backend service

### 1b. Add Config Settings
**File:** `backend/app/config.py`
- Add `QDRANT_URL: str = "http://localhost:6333"`
- Add `QDRANT_COLLECTION: str = "knowledge"`
- Add `EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-0.6B"`
- Add `EMBEDDING_DIM: int = 1024`

### 1c. Add Python Dependencies
**File:** `backend/requirements.txt`
- Add `qdrant-client>=1.7.0`
- Add `sentence-transformers>=3.0.0`
- Add `fastembed>=0.3.0`
- Add `torch --index-url https://download.pytorch.org/whl/cpu` (CPU-only, via separate pip install in Dockerfile)

### 1d. Update Dockerfile
**File:** `backend/Dockerfile`
- Add PyTorch CPU install before `pip install -r requirements.txt`:
  ```
  RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
  ```

---

## Phase 2: Knowledge Service Module

Create `backend/app/services/knowledge/` with 5 files:

### 2a. `__init__.py`
- Exports: `EmbeddingService`, `StorageService`, `IngestionService`, `SearchService`

### 2b. `embedding_service.py`
- Singleton class `EmbeddingService`
- Lazy-loads Qwen3-Embedding-0.6B via `sentence-transformers` on first call
- Lazy-loads FastEmbed `Qdrant/bm25` sparse model on first call
- Methods:
  - `embed_dense(texts: List[str]) -> List[List[float]]` — dense 1024-dim vectors
  - `embed_sparse(texts: List[str]) -> List[SparseVector]` — BM25 sparse vectors
  - `embed_query_dense(query: str) -> List[float]`
  - `embed_query_sparse(query: str) -> SparseVector`
- Qwen3 uses `prompt_name="query"` for queries, no prompt for passages (per Qwen3 docs)
- Thread-safe singleton pattern with `threading.Lock`

### 2c. `storage_service.py`
- Class `StorageService` wrapping `qdrant_client.QdrantClient`
- Methods:
  - `ensure_collection()` — creates collection if not exists, with two named vectors:
    - `"dense"`: size=1024, distance=Cosine
    - `"sparse"`: sparse vector config (for BM25)
  - `upsert_points(points: List[PointStruct])`
  - `hybrid_search(dense_vector, sparse_vector, limit, score_threshold) -> List[ScoredPoint]`
    - Uses Qdrant's `prefetch` API: two prefetch queries (dense KNN + sparse BM25), fused server-side via RRF
  - `delete_by_source(source_id: str)` — delete all points with matching source metadata
  - `collection_info() -> dict` — return point count and status
  - `health_check() -> bool`

### 2d. `ingestion_service.py`
- Class `IngestionService`
- Methods:
  - `ingest_markdown(file_path: str) -> dict` — main entry point
    - Parses `.md` file into knowledge points
    - Each knowledge point = one paragraph under a numbered category heading
    - Stores metadata: `category`, `source_file`, `point_index`, `ingested_at`
  - `_parse_markdown(content: str) -> List[KnowledgePoint]`
    - Splits on `## N. Category Name` headings
    - Under each heading, each non-empty paragraph becomes one knowledge point
    - `KnowledgePoint` dataclass: `text`, `category`, `heading`, `source_file`
  - `_batch_embed_and_upsert(points: List[KnowledgePoint], source_id: str)`
    - Generates dense + sparse embeddings in batches (batch_size=32)
    - Upserts to Qdrant with UUID point IDs
  - `reingest_file(file_path: str)` — deletes old points by source, then re-ingests

### 2e. `search_service.py`
- Class `SearchService`
- Methods:
  - `search(query: str, limit: int = 10, categories: List[str] = None) -> List[SearchResult]`
    - Embeds query (dense + sparse)
    - Calls `storage_service.hybrid_search()` with optional category filter
    - Returns `SearchResult` dataclass: `text`, `category`, `score`, `source_file`
  - `search_for_context(query: str, limit: int = 5) -> str`
    - Calls `search()` and formats results as a context string for LLM injection
    - Format: `"### {category}\n- {text}\n"` grouped by category

---

## Phase 3: REST API

### 3a. Knowledge Endpoints
**New file:** `backend/app/api/v1/endpoints/knowledge.py`

Endpoints:
- `POST /api/v1/knowledge/ingest` — Upload and ingest a `.md` file
  - Accepts `UploadFile`, saves to temp path, calls `IngestionService.ingest_markdown()`
  - Returns `{ "status": "ok", "points_ingested": N, "source_file": "..." }`
- `POST /api/v1/knowledge/search` — Hybrid search
  - Body: `{ "query": str, "limit": int, "categories": List[str] (optional) }`
  - Returns `{ "results": [{ "text": ..., "category": ..., "score": ..., "source_file": ... }] }`
- `GET /api/v1/knowledge/status` — Collection status
  - Returns `{ "collection": "knowledge", "point_count": N, "status": "..." }`
- `DELETE /api/v1/knowledge/source/{source_id}` — Delete all points from a source file

### 3b. Register Router
**File:** `backend/app/api/v1/__init__.py`
- Import knowledge router
- Add: `router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])`

---

## Phase 4: App Startup Integration

### 4a. Lifespan Init
**File:** `backend/app/main.py`
- In `lifespan()`, after database init:
  - Import `StorageService`, call `ensure_collection()` with error handling
  - Log success/failure (non-fatal — app runs without Qdrant, just no knowledge search)

### 4b. Health Check
**File:** `backend/app/utils/health.py`
- Add Qdrant health check block:
  ```python
  try:
      from qdrant_client import QdrantClient
      client = QdrantClient(url=settings.QDRANT_URL, timeout=5)
      client.get_collections()
      services["qdrant"] = "ok"
  except:
      services["qdrant"] = "error"
  ```

---

## Phase 5: Skill Integration

### 5a. Add Knowledge Context to Base Skill
**File:** `backend/app/services/agent/skills/base_skill.py`
- Add method `_get_knowledge_context(query: str, limit: int = 5) -> str`
  - Imports `SearchService`, calls `search_for_context()`
  - Returns formatted context string or empty string on error
  - Errors are logged but never block analysis
- Skills can call `context = self._get_knowledge_context(address)` in their `analyze()` method and prepend it to their LLM prompt

---

## Phase 6: Dockerfile Update

**File:** `backend/Dockerfile`
- Add CPU-only PyTorch install before requirements:
  ```dockerfile
  RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
  ```
- This keeps the image size manageable (~800MB for CPU torch vs ~2GB+ for CUDA)

---

## Files Summary

### New Files (7)
| File | Purpose |
|------|---------|
| `backend/app/services/knowledge/__init__.py` | Module exports |
| `backend/app/services/knowledge/embedding_service.py` | Qwen3 dense + BM25 sparse embeddings |
| `backend/app/services/knowledge/storage_service.py` | Qdrant client wrapper |
| `backend/app/services/knowledge/ingestion_service.py` | Markdown parser + batch embedder |
| `backend/app/services/knowledge/search_service.py` | Hybrid search + context formatting |
| `backend/app/api/v1/endpoints/knowledge.py` | REST API endpoints |
| `.env.example` | Document new env vars (QDRANT_URL) |

### Modified Files (6)
| File | Change |
|------|--------|
| `docker-compose.yml` | Add qdrant service, env vars, depends_on |
| `backend/app/config.py` | Add QDRANT_URL, QDRANT_COLLECTION, EMBEDDING_MODEL, EMBEDDING_DIM |
| `backend/requirements.txt` | Add qdrant-client, sentence-transformers, fastembed |
| `backend/Dockerfile` | Add PyTorch CPU install |
| `backend/app/api/v1/__init__.py` | Register knowledge router |
| `backend/app/main.py` | Qdrant collection init on startup |
| `backend/app/utils/health.py` | Qdrant health check |
| `backend/app/services/agent/skills/base_skill.py` | Add `_get_knowledge_context()` method |

---

## Verification Plan

1. **Docker build**: `docker compose build backend` — verify Dockerfile installs torch, sentence-transformers, fastembed without errors
2. **Services up**: `docker compose up -d` — verify qdrant container is healthy
3. **Health check**: `curl http://localhost:8000/health` — verify `qdrant: "ok"` appears
4. **Ingest test**: Upload a sample `.md` knowledge file via `POST /api/v1/knowledge/ingest`
5. **Search test**: `POST /api/v1/knowledge/search` with `{"query": "school district ratings"}` — verify results return with scores
6. **Status check**: `GET /api/v1/knowledge/status` — verify point count matches ingested paragraphs
7. **Integration test**: Trigger a property analysis and verify knowledge context is included in skill prompts (check logs)
