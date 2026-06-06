# 🧠 Memory Wiki

A service that ingests conversation transcripts, generates structured memories using an LLM, stores them in a file-system-like structure in cloud object storage, and exposes them via unix-style REST endpoints.

## Quick Start

```bash
# 1. Clone and configure
git clone <repo-url> && cd memory-wiki
cp .env.example .env
# Edit .env and set your LLM_API_KEY (Mistral by default)

# 2. Start everything
docker compose up --build -d

# 3. Run database migrations
docker compose run --rm api alembic upgrade head

# 4. (Optional) Seed with sample transcripts
docker compose run --rm api python -m scripts.seed_data

# 5. Verify
curl http://localhost:8000/api/v1/health
```

**That's it.** The API is at `http://localhost:8000`, MinIO console at `http://localhost:9001` (minioadmin/minioadmin).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client / cURL                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                   FastAPI Application                           │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐   │
│  │ POST/GET     │  │ GET /tree    │  │ GET /search         │   │
│  │ /transcripts │  │ GET /file    │  │ (grep)              │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬──────────┘   │
└─────────┼─────────────────┼─────────────────────┼──────────────┘
          │                 │                     │
    ┌─────▼─────┐     ┌────▼─────┐         ┌─────▼────┐
    │ PostgreSQL │     │  MinIO   │         │  MinIO   │
    │ (metadata) │     │   (S3)   │         │   (S3)   │
    └─────┬─────┘     └──────────┘         └──────────┘
          │
    ┌─────▼─────┐
    │   Redis   │
    │  (queue)  │
    └─────┬─────┘
          │
    ┌─────▼──────────────────────────────────────────┐
    │              Celery Worker                      │
    │  ┌────────────┐  ┌───────────┐  ┌───────────┐  │
    │  │ LLM Extract│→ │  Merge/   │→ │ Write to  │  │
    │  │   (LLM)    │  │  Create   │  │   MinIO   │  │
    │  └────────────┘  └───────────┘  └───────────┘  │
    └─────────────────────────────────────────────────┘
```

### Components

| Component | Technology | Purpose |
|:----------|:-----------|:--------|
| **API** | FastAPI | REST endpoints for transcripts and memory tree operations |
| **Database** | PostgreSQL 16 | Transcript storage, processing status, idempotency tracking |
| **Object Storage** | MinIO (S3-compatible) | Memory file tree — the actual "second brain" |
| **Queue** | Redis + Celery | Async background processing with retries |
| **LLM** | Mistral (configurable) | Memory extraction and intelligent merging |

---

## Memory Design Philosophy

### Why Entity-Centric, Not Transcript-Centric?

Most naive implementations would create one memory file per transcript. This is wrong for a "second brain" — it forces the user to remember *which conversation* contained *which fact*.

Instead, this system organizes memories by **entity** (people, topics, events):

```
memories/
├── people/
│   ├── john_doe/
│   │   └── profile.md        ← everything about John, across all conversations
│   └── sarah_chen/
│       └── profile.md
├── topics/
│   ├── project_atlas/
│   │   └── overview.md       ← all facts, decisions, action items about Atlas
│   └── notification_system/
│       └── overview.md
├── events/
│   ├── 2026-06-05_weekly_standup.md
│   └── 2026-06-05_design_review.md
└── _meta/
    ├── index.json             ← master entity registry
    └── graph.json             ← entity relationship graph
```

When a new transcript mentions "John" who is already in memory, the system **merges** the new information — it doesn't create a duplicate. This is the key insight.

### Why Markdown with YAML Frontmatter?

- **Human-readable**: You can `cat` a file and immediately understand it
- **Machine-parseable**: YAML frontmatter provides structured metadata for the API
- **LLM-friendly**: Both input and output formats that LLMs handle well
- **Grep-friendly**: Full-text search works naturally on Markdown

### Merge Strategy

| File Type | Strategy | Example |
|:----------|:---------|:--------|
| Person profile | **Upsert** — new facts update/extend, stale facts get replaced | Title changed → update, don't duplicate |
| Topic overview | **Upsert + Append** — facts merge, decisions/actions append | New decision → add to list |
| Event summary | **Create only** — each event is unique | Each meeting gets its own file |

---

## API Reference

### Transcript Endpoints

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `POST` | `/api/v1/transcripts` | Ingest a transcript (returns 202 Accepted) |
| `GET` | `/api/v1/transcripts` | List all transcripts (paginated) |
| `GET` | `/api/v1/transcripts/:id` | Get transcript by ID |
| `GET` | `/api/v1/transcripts/:id/status` | Check memory generation status |
| `POST` | `/api/v1/transcripts/:id/retry` | Re-enqueue a failed transcript |

**Why 202 Accepted?** Memory generation is async. Returning 201 would imply the resource is fully created, but memories haven't been generated yet. 202 accurately communicates "accepted for processing."

### Memory Endpoints (Unix-style)

| Operation | Unix Equiv | Endpoint | Query Params |
|:----------|:-----------|:---------|:-------------|
| List directory | `ls` | `GET /api/v1/memories/tree` | `path=/`, `depth=0` |
| Read file | `cat` | `GET /api/v1/memories/file` | `path=/people/john_doe/profile.md` |
| Search | `grep -rn` | `GET /api/v1/memories/search` | `q=atlas`, `path=/`, `case_insensitive=true` |

### Error Handling

All errors follow [RFC 7807 (Problem Details)](https://tools.ietf.org/html/rfc7807):

```json
{
  "type": "https://memorywiki.dev/errors/not-found",
  "title": "Transcript Not Found",
  "status": 404,
  "detail": "No transcript with ID 'abc-123' exists.",
  "instance": "/api/v1/transcripts/abc-123"
}
```

---

## Background Processing

### Reliability Features

| Feature | Implementation |
|:--------|:---------------|
| **Retries** | Exponential backoff with jitter, max 3 retries |
| **Idempotency** | Entity-level tracking — re-processing skips already-written entities |
| **Late acknowledgment** | Tasks ack only after completion; crashes re-queue the task |
| **Timeouts** | Soft limit (120s) raises exception; hard limit (180s) kills worker |
| **Status tracking** | `pending → processing → completed/failed` with error details |

### Pipeline Flow

1. **POST /transcripts** → Save to DB, enqueue Celery task, return 202
2. **Worker picks up** → Fetch transcript, mark `processing`
3. **LLM extraction** → Structured JSON output with people, topics, events, relationships
4. **For each entity** → Check if exists in S3 → Create new or merge with existing
5. **Update `_meta/index.json`** → Entity registry for fast lookups
6. **Mark `completed`** → Status queryable via API

---

## Key Tradeoffs

### MinIO over local filesystem
The spec says "cloud object storage." A local filesystem would be simpler but doesn't demonstrate cloud infrastructure understanding. MinIO provides a real S3-compatible API that runs locally — same code works against AWS S3 in production.

### Celery + Redis over background threads
FastAPI's `BackgroundTasks` would be simpler but offers zero reliability — if the process crashes, the task is gone forever. Celery provides retries, dead letter queues, monitoring (Flower), and horizontal scaling — all essential for a system where data loss is unacceptable.

### Markdown + YAML frontmatter over pure JSON
JSON would be easier to parse but harder to read and grep. Markdown is the native language of LLMs and humans alike. YAML frontmatter gives us structured metadata without sacrificing readability.

### Entity-centric over transcript-centric memory
A 1:1 transcript→file mapping is simpler but creates information silos. Entity-centric organization enables cross-referencing ("what do I know about John across all conversations?") which is the core value proposition of a second brain.

### 202 Accepted over 201 Created
Subtle but important. 201 implies the full resource (transcript + memories) is ready. 202 accurately communicates that the transcript has been accepted for async processing and memories are not yet available.

---

## Testing

```bash
# Run all tests
make test

# Run by layer
make test-unit           # Fast, no external dependencies
make test-integration    # Requires Docker services
make test-e2e            # Full pipeline test

# With coverage
make test-cov
```

### Testing Pyramid

| Layer | Count | What's Tested |
|:------|:------|:-------------|
| **Unit** | 36 | Extraction parsing, schema validation, path normalization, merge logic, guardrails |
| **Integration** | 21 | API endpoints, retry logic, S3 operations, error handling |
| **E2E** | 2 | Full ingest → extract → query pipeline |

---

## What I'd Do With More Time

1. **Semantic search** — Add embedding-based grep using pgvector or ChromaDB for "find memories *about* X" vs "find memories *mentioning* X"
2. **Memory versioning** — S3 object versioning + diff view to see how memories evolved
3. **WebSocket status** — Real-time processing updates instead of polling
4. **Conflict resolution** — When two transcripts are processed simultaneously for the same entity, detect and resolve merge conflicts
5. **Prompt evaluation suite** — Automated evals comparing extraction quality across prompt versions
6. **Multi-tenant support** — User-scoped memory trees with auth
7. **Chunking for long transcripts** — Split transcripts exceeding the LLM context window
8. **Memory decay** — Confidence scores that decrease over time for unconfirmed facts
9. **Input guardrails** — Max transcript length enforcement, content validation, and LLM output schema enforcement (e.g. reject extractions that return no entities or malformed JSON)

---

## Project Structure

```
src/
├── main.py                    # FastAPI app factory
├── config.py                  # Pydantic Settings
├── api/
│   ├── router.py              # Route aggregation
│   ├── transcripts.py         # Transcript CRUD endpoints
│   ├── memories.py            # Memory tree/file/search endpoints
│   ├── health.py              # Liveness probe
│   └── errors.py              # RFC 7807 error handlers
├── models/
│   ├── transcript.py          # SQLAlchemy ORM model
│   └── schemas.py             # Pydantic request/response schemas
├── services/
│   ├── transcript_service.py  # Transcript business logic
│   ├── memory_service.py      # Memory tree operations
│   └── storage_service.py     # S3 abstraction layer
├── workers/
│   ├── celery_app.py          # Celery configuration
│   ├── tasks.py               # Task definitions with retry logic
│   └── pipeline.py            # Memory extraction + merge pipeline
├── llm/
│   ├── client.py              # LLM client with retries
│   ├── prompts.py             # All prompt templates
│   ├── extraction.py          # Structured output parsing
│   └── merger.py              # Intelligent merge logic
└── db/
    ├── session.py             # Database session management
    └── migrations/            # Alembic migrations
```
