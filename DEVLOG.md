# RAG Chatbot — Development Log
**Branch:** `dev/embedding-pipeline`  
**Developer:** Dev B (Embeddings / Ingestion / Pipeline)  
**Last updated:** March 2026

---

## What Was Built

### Phase 1 — Shared Contract (`shared/`)
The foundation both developers import from. Built before any feature code.

| File | Purpose |
|---|---|
| `shared/schemas.py` | All Pydantic models — `ChunkInput`, `ChunkDocument`, `QueryRequest`, `QueryResponse` |
| `shared/config.py` | Every constant in one place, overridable via `.env` |
| `shared/database.py` | MongoDB connection + index initialization |

**Key design decision:** `ChunkInput` and `ChunkDocument` are two separate types.
Dev A produces `ChunkInput` (text only). Dev B fills in `embedding`, `embedding_model`, `embedded_at` to produce `ChunkDocument`. Neither dev touches the other's fields.

---

### Phase 2 — Infrastructure Setup
| Tool | How it runs |
|---|---|
| MongoDB 7.0 | Docker container (`docker compose up -d`) |
| Mongo Express (DB UI) | Docker container → `http://localhost:8081` |
| Ollama | Native on Mac (GPU access, no Docker) |
| Embedding model | `nomic-embed-text` via Ollama — 768-dim vectors |
| LLM | `mistral:7b` via Ollama — pulled, ready for later |

**Key design decision:** Ollama runs natively, not in Docker.
Docker on Mac has no GPU passthrough. Running Ollama in a container would mean CPU-only inference — too slow for `mistral:7b`. The containerized FastAPI app will reach Ollama via `host.docker.internal:11434`.

---

### Phase 3 — Embedding Pipeline (`embedding/`)

| File | Purpose |
|---|---|
| `embedding/ollama_client.py` | Thin HTTP wrapper — `get_embedding(text)` → `list[float]` |
| `embedding/embedder.py` | `embed_chunk(ChunkInput)` → `ChunkDocument` with vector filled in |

Each file was tested in isolation with a dedicated test script before moving on.

---

### Phase 4 — Ingestion Pipeline (`ingestion/`)

| File | Purpose |
|---|---|
| `ingestion/loader.py` | Opens PDF, extracts text page by page using `pdfplumber` |
| `ingestion/chunker.py` | Splits pages into overlapping chunks using sentence-aware strategy |

**Chunking strategy:** sentence-aware, 512 chars per chunk, 64 chars overlap.
Sentences are never cut mid-way. Overlap preserves context at chunk boundaries.

---

### Phase 5 — Full Pipeline (`pipeline.py`)
Single script that runs the complete flow end to end:

```
PDF on disk
    ↓  loader.py       extract text page by page
    ↓  chunker.py      split into 187 chunks (filtered: < 50 chars removed)
    ↓  embedder.py     embed each chunk via nomic-embed-text
    ↓  MongoDB         insert 768-dim vectors into `chunks` collection
```

Includes a pre-flight check (Ollama running?), duplicate detection (asks before re-embedding), and progress logging.

---

## Problems Faced & Solutions

### Problem 1 — `pip` and `python` pointing to different environments
**Symptom:**
```
ModuleNotFoundError: No module named 'bson'
```
Even after running `pip install -r requirements.txt`, the error persisted.

**Root cause:**
```bash
which python → /opt/anaconda3/bin/python
which pip    → /Library/Frameworks/Python.framework/Versions/3.11/bin/pip
```
`pip` was installing into a completely different Python than the one being executed.

**Solution:**
Always use `python -m pip install` instead of `pip install`. This guarantees packages install into the same Python that runs the code.
```bash
python -m pip install -r requirements.txt
```

---

### Problem 2 — Docker daemon not running
**Symptom:**
```
Cannot connect to the Docker daemon at unix:///Users/mac/.docker/run/docker.sock.
Is the docker daemon running?
```

**Root cause:** Docker Desktop is not a background service on Mac — it must be launched manually as an application.

**Solution:** Open Docker Desktop from Spotlight (Cmd + Space → "Docker"), wait for the whale icon in the menu bar to stop animating, then re-run `docker compose up -d`.

---

### Problem 3 — Broken text extraction from PDF
**Symptom:** First test run with `pypdf` showed garbled text:
```
"Tableof contents"
"AuthentificationSignup 6OrganizationSignup 7"
"Listingcategories 21Createne"
```
Words were fused together with missing spaces — a known `pypdf` issue with PDFs using custom fonts or tight kerning.

**Root cause:** `pypdf`'s text extractor does not reconstruct word spacing correctly for this PDF.

**Solution:** Switched to `pdfplumber` which uses a different extraction engine and handles spacing correctly.
```bash
python -m pip install pdfplumber
```
Updated `requirements.txt`: replaced `pypdf>=4.2.0` with `pdfplumber>=0.11.0`.

After the switch:
```
"Table of contents"
"Authentification Sign up 6"
"Listing categories 21"
```

---

### Problem 4 — Ollama GPU not detected on Mac
**Symptom:** Ollama logs showed:
```
inference compute: cpu
total: 16.0 GiB / available: 5.6 GiB
```

**Root cause:** Mac Metal GPU was not detected by this version of Ollama (0.18.1). Embedding runs on CPU.

**Impact:** `nomic-embed-text` embedding is slightly slower but fully functional. `mistral:7b` will be slower for generation — acceptable for development.

**Status:** Not blocking. Will revisit if generation latency is unacceptable during LLM integration phase.

---

## Current State of the Database

- **Collection:** `rag_chatbot.chunks`
- **Documents:** ~180 chunks
- **Source:** `DocCerts - Documentation.pdf` (152 pages, 56,677 chars)
- **Embedding model:** `nomic-embed-text` (768 dimensions)
- **Browsable at:** `http://localhost:8081` (Mongo Express)

Each document in MongoDB has this structure:
```json
{
  "source_file": "DocCerts - Documentation.pdf",
  "chunk_index": 42,
  "text": "To create a new certificate, navigate to...",
  "char_count": 312,
  "metadata": {
    "doc_type": "pdf",
    "page_number": 37,
    "section_title": null,
    "language": "en",
    "tags": []
  },
  "embedding": [ ...768 floats... ],
  "embedding_model": "nomic-embed-text",
  "embedded_at": "2026-03-18T18:45:00Z"
}
```

---

## For Your Coworker (Dev A)

To reproduce the database locally:
```bash
git clone <repo-url>
git checkout dev/embedding-pipeline

# Drop the PDF in the project root:
# "DocCerts - Documentation.pdf"

python -m pip install -r requirements.txt
docker compose up -d
python pipeline.py
```

MongoDB will be populated in ~5 minutes.

---

## What Comes Next

| Step | Owner | Status |
|---|---|---|
| `retrieval/similarity.py` — cosine similarity in numpy | Dev B | 🔜 Next |
| `retrieval/retriever.py` — load vectors, run search | Dev B | 🔜 Next |
| `ingestion/` for other file types (MD, TXT, DOCX) | Dev A | 🔜 Parallel |
| `api/main.py` — FastAPI app skeleton | Dev A | 🔜 Parallel |
| `generation/llm_client.py` — Ollama LLM wrapper | Dev B | After retrieval |
