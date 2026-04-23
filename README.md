# Broadcast AI — AI Assistant for Advertising & Business Department

> Hai Phong Radio and Television Station (BPTTH)

An AI-powered chat assistant that helps the Advertising & Business Department look up pricing, calculate advertising costs, and get instant answers from internal documents — without digging through PDFs manually.

---

## The Problem

The Advertising & Business Department at BPTTH works with multiple overlapping price tables (THP, HP channels, radio, digital, documentaries), each governed by separate official decisions (QĐ 413, 414, 415). Staff regularly need to:

- Find the right unit price for a given time slot and customer type
- Calculate total contract costs including discounts
- Determine which pricing decision applies (Hai Phong client vs. out-of-province)

Doing this manually is slow and error-prone, especially under client pressure.

---

## The Solution

A conversational AI assistant backed by a **Knowledge Graph** built from the station's actual documents. Instead of keyword search, the system understands *intent* and retrieves *contextually relevant* information.

**Two modes:**
- **Q&A mode** — answers pricing and policy questions with source citations
- **Calculate mode** — computes exact costs using dedicated Python pricing tools (LLM handles presentation, not arithmetic)
- **Quote mode** - In Progressing..

---

## How It Works

```
User message
    │
    ├── Intent classifier  →  "qa" or "calculate"
    │
    ├── GraphRAG Hybrid Retrieval (runs in parallel)
    │     ├── Vector search (semantic similarity)
    │     ├── Graph traversal (entity relationships)
    │     └── Fulltext search (keyword matching)
    │
    ├── "qa"         → LLM generates answer from retrieved context
    └── "calculate"  → LLM calls Python pricing tools → formats result
```

### Knowledge Base (Neo4j)

The core of the system. Source documents are processed into a **Knowledge Graph** where:
- Text is split into chunks and embedded with a Vietnamese embedding model
- Entities (time slots, prices, channels, customer types) and their relationships are extracted by an LLM
- Three indexes enable hybrid search: vector, fulltext, and entity-level

Built with a **customized version of [Neo4j LLM Graph Builder](https://neo4j.com/labs/genai-ecosystem/llm-graph-builder/)**, adapted for Vietnamese and BPTTH-specific content.

### GraphRAG Hybrid

Results from all three search strategies are merged and re-ranked. Chunks that appear in multiple search types (e.g., both vector and fulltext) are ranked higher — improving answer precision for domain-specific terms like slot codes (HP8, T1, S3).

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, LangGraph |
| LLM | Viettel AI API |
| Embedding | `AITeamVN/Vietnamese_Embedding_v2` (self-hosted via Infinity) |
| Knowledge Graph | Neo4j (AuraDB) |
| Frontend | React, Vite, TypeScript, Tailwind CSS |

---

## Quick Start

**Requirements:** Python ≥ 3.10, Node.js ≥ 18, pnpm, uv, Docker, Neo4j with APOC

```bash
# 1. Install dependencies
uv sync
cd frontend && pnpm install && cd ..

# 2. Configure environment
cp backend/.env.example backend/.env   # fill in NEO4J_*, INFINITY_URL, VIETTEL_*

# 3. Start embedding server
docker run -d -p 7997:7997 --gpus all \
  -v ./models/local_model_AITeamVN_Vietnamese_Embedding_v2:/models/Vietnamese_Embedding_v2 \
  michaelf34/infinity:latest v2 \
  --model-id /models/Vietnamese_Embedding_v2 --port 7997

# 4. Build the Knowledge Base
# Upload documents via Neo4j LLM Graph Builder → point to your Neo4j instance

# 5. Run backend
PYTHONPATH=backend uv run uvicorn backend.main:app --reload --port 8000

# 6. Run frontend
cd frontend && pnpm dev   # http://localhost:5173
```

---

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Chat (full response) |
| `/api/chat/stream` | POST | Chat with SSE token streaming |
| `/api/sessions` | GET | List conversation sessions |
| `/api/sessions/{id}` | DELETE | Delete a session |
| `/health` | GET | Health check |

---

## Testing

```bash
# Unit tests (17 test cases)
PYTHONPATH=backend uv run python -m pytest tests/test_nodes.py -v

# RAG quality benchmark (RAGAS metrics)
PYTHONPATH=backend uv run python benchmark/run.py
```

---

*Internal use — Hai Phong Radio and Television Station · v0.1.0 · April 2026*
