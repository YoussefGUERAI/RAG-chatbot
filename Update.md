# Update Log

## Summary

This document lists every change applied to the codebase, what was wrong, and why it needed to be fixed.

---

## 1. Created `ingestion/__init__.py`

**Why:** Every other package (`api`, `embedding`, `generation`, `retrieval`, `shared`) had an `__init__.py`. The `ingestion` package was missing one, breaking the explicit package design and causing inconsistencies with some tooling and import styles.

---

## 2. `ingestion/chunker.py` — Overlap logic bug + performance fix

**Why (bug):** The overlap calculation collected sentences by character count but did not account for the space characters added by `" ".join(...)` when the chunk is assembled. This caused the actual overlap text to be slightly longer than the configured `CHUNK_OVERLAP` value, making chunk boundaries inconsistent.

**Fix:** A `sep` variable now adds `1` for each space separator between sentences when measuring overlap length.

**Why (performance):** `list.insert(0, item)` is O(n) per call — inserting at the front shifts every existing element. Inside a loop, this becomes O(n²). For documents with many short sentences this was measurably slow.

**Fix:** Replaced `insert(0, ...)` with `append(...)` followed by a single `list.reverse()` call, making the loop O(n) overall.

---

## 3. `ingestion/chunker.py` — Function signature formatting

**Why:** Missing space after comma in `chunk_pages(pages: list[tuple[int, str]],source_file: str)` violated PEP 8 and broke consistency with the rest of the codebase.

---

## 4. `ingestion/loader.py` — Specific exception handling

**Why:** The original code only caught `FileNotFoundError`. Any other failure (permission denied, corrupted PDF, encrypted PDF, file too large) would surface as a raw, unhelpful exception. Users had no indication of what went wrong or how to fix it.

**Fix:** Added specific catches for `PermissionError`, `MemoryError`, and a broad fallback for anything else pdfplumber raises, each with a clear message.

---

## 5. `embedding/ollama_client.py` — Timeout exception + error truncation

**Why:** `httpx.TimeoutException` was not caught. If Ollama was slow to respond (e.g. model still loading), the exception would bubble up unhandled with no useful message. Additionally, `e.response.text` on an error could be an entire HTML error page, flooding logs.

**Fix:** Added `httpx.TimeoutException` handler with a clear message. Truncated raw error text to 500 characters.

---

## 6. `generation/llm_client.py` — Timeout exception + empty response check

**Why (timeout):** Same issue as `ollama_client.py` — `httpx.TimeoutException` was unhandled. LLM generation on CPU can be slow; a timeout would crash without a readable error.

**Why (empty response):** The LLM can return a valid JSON response with an empty `"response"` field. The original code would return an empty string silently, giving the user a blank answer with no indication of failure.

**Fix:** Added timeout handler and an explicit check that raises `RuntimeError` if the response is an empty string after stripping.

---

## 7. `shared/database.py` — Connection ping at startup

**Why:** `MongoClient()` does not verify the connection immediately — it connects lazily. If MongoDB was not running, the error would only appear when the first database operation was attempted, mid-request, with a confusing pymongo timeout error.

**Fix:** After creating the client, a `ping` command is sent immediately. If MongoDB is unreachable, a `RuntimeError` with a clear message is raised right away, before any request is processed. `serverSelectionTimeoutMS=5000` prevents the ping from hanging indefinitely.

---

## 8. `shared/schemas.py` — Pydantic v2 validators

**Why:** `PyObjectId` used the Pydantic v1 `__get_validators__` class method, which is deprecated in Pydantic v2. The project already requires `pydantic>=2.7.0`. Mixing v1 and v2 patterns causes deprecation warnings and will break with a future Pydantic version.

**Fix:** Replaced the entire class with a Pydantic v2 `Annotated` type using `BeforeValidator`, `PlainSerializer`, and `WithJsonSchema` — the idiomatic v2 approach.

---

## 9. `pipeline.py` — CLI arguments replacing hardcoded path

**Why (hardcoded path):** `PDF_PATH = "DocCerts - Documentation.pdf"` was hardcoded at the top of the script. Processing any other document required editing source code, which is not acceptable for a tool meant to be run repeatedly.

**Why (`input()` hang):** `input()` blocks indefinitely when stdin is closed — which is the case in Docker containers, CI/CD pipelines, and any non-interactive shell. The script would hang with no output or error.

**Fix:** Added `argparse` with a required `--file` argument and a `--yes` flag that skips the confirmation prompt. `input()` is now wrapped in a `try/except EOFError` so it fails cleanly in non-interactive environments instead of hanging.

---

## 10. `embedding/embedder.py` — Parallel embedding

**Why:** The original implementation made one sequential HTTP request to Ollama per chunk. For a document with 200 chunks, that is 200 back-to-back round trips. The embedding model is fast, but network latency and per-request overhead add up significantly.

**Fix:** `embed_chunks` now uses `ThreadPoolExecutor` to embed multiple chunks concurrently. The number of workers is taken from `EMBEDDING_BATCH_SIZE` in config (capped at 8 to avoid overwhelming Ollama). Chunk ordering is preserved regardless of completion order.

---

## 11. `tests/test_ingestion.py` — Proper pytest suite

**Why:** The original test file used `print()` for all verification — there were no `assert` statements. Running `pytest` on it would always pass, even if every function was broken, because pytest only detects failures through exceptions or assertion errors. The tests were also structured for manual `python test_ingestion.py` execution only, not for automated test discovery.

**Fix:** Rewrote as a proper pytest suite with 6 test functions, each using `assert` with descriptive failure messages. A `pytest.fixture` provides the loaded pages and automatically `pytest.skip`s the tests if the PDF file is not present (so CI does not break). The `__main__` block is kept for manual inspection runs.

---

## 12. `api/routes/ingest.py` — New `/ingest` endpoint

**Why:** The README, project structure, and `api/routes/` directory all indicated a `POST /ingest` endpoint, but the file was never implemented. Users had no way to add documents via the API — they were required to run `pipeline.py` manually from the command line.

**What it does:** Accepts a PDF file upload, runs the full ingestion pipeline (load → chunk → embed → save to MongoDB), and returns a JSON response with `filename`, `pages_loaded`, `chunks_created`, and `chunks_embedded`. Temporary files are always cleaned up, even on error.

---

## 13. `api/main.py` — Registered the `/ingest` router

**Why:** Without this line, the new `/ingest` endpoint would exist in code but never be mounted on the app, making it unreachable.

---

---

# Setup Guide — Run the Project

Follow these steps in order.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://python.org) |
| Docker Desktop | latest | [docker.com](https://docker.com) |
| Ollama | latest | [ollama.com](https://ollama.com) |

---

## Step 1 — Install Python dependencies

```bash
pip install -r requirements.txt
```

---

## Step 2 — Configure environment

```bash
copy .env.example .env
```

The defaults in `.env` work out of the box for a local setup. Edit only if you need different ports or model names.

---

## Step 3 — Start MongoDB

```bash
docker compose up -d
```

This starts MongoDB on port `27017` and Mongo Express (database browser) on port `8081`.

Verify: open `http://localhost:8081` in a browser — you should see the Mongo Express UI.

---

## Step 4 — Start Ollama and pull models

```bash
ollama serve
```

Open a second terminal and pull the two required models:

```bash
ollama pull nomic-embed-text
ollama pull mistral:7b
```

`nomic-embed-text` (~270 MB) is used for embeddings. `mistral:7b` (~4 GB) is the language model. The pull only happens once; after that they are cached locally.

---

## Step 5 — Ingest a PDF

```bash
python pipeline.py --file "DocCerts - Documentation.pdf"
```

To skip the confirmation prompt (e.g. re-ingesting):

```bash
python pipeline.py --file "DocCerts - Documentation.pdf" --yes
```

Wait for the pipeline to finish. You will see progress for each embedding step. On CPU this takes a few minutes depending on document size.

---

## Step 6 — Start the API

```bash
python -m uvicorn api.main:app --reload
```

The API will be available at `http://localhost:8000`.

Interactive API docs: `http://localhost:8000/docs`

---

## Step 7 — Ask a question

Using curl:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What is this document about?\"}"
```

Or use the Swagger UI at `http://localhost:8000/docs` — click `/query`, then "Try it out".

---

## Step 8 — (Optional) Ingest via API

You can now upload PDFs directly through the API without using the command line:

```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@path/to/your/document.pdf"
```

---

## Step 9 — Run the test suite

```bash
pytest tests/test_ingestion.py -v
```

Tests will be skipped automatically if the PDF file is not present in the project root.

---

## Quick reference

| Service | URL |
|---------|-----|
| API | `http://localhost:8000` |
| API docs (Swagger) | `http://localhost:8000/docs` |
| MongoDB browser | `http://localhost:8081` |
| Ollama | `http://localhost:11434` |
