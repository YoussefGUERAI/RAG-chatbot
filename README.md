# RAG Chatbot — Shared Interface Contract

This folder (`shared/`) is the **only** place where cross-developer types and
configuration live. Both Dev A and Dev B import from here. **Never duplicate
these definitions in your own module.**

---

## Project Structure

```
rag_chatbot/
│
├── shared/                  ← YOU ARE HERE (touch together, not alone)
│   ├── __init__.py
│   ├── schemas.py           ← Pydantic models (the handoff types)
│   ├── config.py            ← All constants and env vars
│   └── database.py          ← MongoDB connection + index init
│
├── ingestion/               ← Dev A owns this
│   ├── loader.py            ← Reads PDF / MD / TXT → RawDocument
│   ├── chunker.py           ← RawDocument → list[ChunkInput]
│   └── writer.py            ← Saves ChunkInput to MongoDB (no embedding yet)
│
├── embedding/               ← Dev B owns this
│   ├── embedder.py          ← ChunkInput → embedding vector via Ollama
│   ├── batch_runner.py      ← Reads un-embedded chunks, fills embedding field
│   └── ollama_client.py     ← Thin async wrapper around Ollama HTTP API
│
├── retrieval/               ← Both review, Dev B leads
│   ├── retriever.py         ← Loads vectors from Mongo, runs cosine similarity
│   └── similarity.py        ← Pure numpy cosine implementation (no frameworks)
│
├── generation/              ← Dev B owns this
│   ├── prompt.py            ← Builds the prompt string from chunks + question
│   └── llm_client.py        ← Calls Ollama /api/generate
│
├── api/                     ← Dev A owns this
│   ├── main.py              ← FastAPI app + lifespan (calls init_db)
│   ├── routes/
│   │   ├── query.py         ← POST /query
│   │   └── ingest.py        ← POST /ingest (upload a document)
│   └── dependencies.py      ← Shared FastAPI deps (DB, settings)
│
├── evaluation/              ← Dev B owns this
│   ├── metrics.py           ← Precision@K, MRR, latency
│   └── test_queries.json    ← Ground-truth Q&A pairs for eval
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## The Handoff Point

The **only** interface between Dev A's work and Dev B's work is:

```python
class ChunkInput(BaseModel):
    text: str
    source_file: str
    chunk_index: int
    metadata: ChunkMetadata
```

- Dev A produces `list[ChunkInput]` → saves to MongoDB (without embedding).
- Dev B reads un-embedded docs from MongoDB → fills `embedding`, `embedding_model`, `embedded_at`.

**Agree on `ChunkInput` before Week 4. Do not change it without telling your coworker.**

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

```bash
cp .env.example .env
```

All defaults in `config.py` work for local development without a `.env` file.

---

## Running for the first time

```bash
pip install -r requirements.txt

# Start MongoDB (make sure it's running locally on port 27017)
# Start Ollama (Dev B will set this up)

# Run the API
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Design Choices

| Decision | What it enables |
|---|---|
| Pydantic models | Validation, FastAPI integration, self-documentation |
| `ChunkInput` vs `ChunkDocument` | Dev A and Dev B work independently |
| Optional embedding fields | Ingestion and embedding pipelines decouple |
| Sparse index on `embedded_at` | Efficient "find un-embedded chunks" query |
| `lru_cache` on settings | Single config read, `.env` override support |
| Local Ollama models | No cost, no internet dependency |
| Manual cosine similarity | Educational, simple, swappable later |
| `doc_type_filter` in API | Pre-filter escape hatch for scale |
| Nested `ChunkMetadata` | Extensible without schema changes |