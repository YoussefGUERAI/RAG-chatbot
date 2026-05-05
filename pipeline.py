"""
pipeline.py
===========
Wires everything together in one script:
  1. Load PDF         → list of (page, text)
  2. Chunk pages      → list[ChunkInput]
  3. Filter bad chunks → remove anything too short to be useful
  4. Embed chunks     → list[ChunkDocument]
  5. Save to MongoDB  → done

Usage:
    python pipeline.py --file path/to/document.pdf
    python pipeline.py --file path/to/document.pdf --yes
"""

import argparse
import sys
import time
from ingestion.loader import load_pdf
from ingestion.chunker import chunk_pages
from embedding.embedder import embed_chunks
from embedding.ollama_client import is_ollama_running
from shared.database import get_collection, init_db
from shared.config import get_settings

MIN_CHUNK_CHARS = 50


def run_pipeline(pdf_path: str, auto_confirm: bool = False) -> None:
    settings = get_settings()
    print("\n" + "=" * 55)
    print("  RAG Pipeline — PDF → MongoDB")
    print("=" * 55 + "\n")

    # ── Step 0: Pre-flight checks ──────────────────────
    print("0. Pre-flight checks...")

    if not is_ollama_running():
        print(f"   ❌ Ollama is not running at {settings.OLLAMA_BASE_URL}")
        print("   → Start it with: ollama serve")
        sys.exit(1)

    print(f"   ✅ Ollama is running")

    col = get_collection()
    existing = col.count_documents({"source_file": pdf_path})
    if existing > 0:
        print(f"   ⚠️  Found {existing} existing chunks for '{pdf_path}' in MongoDB.")
        if auto_confirm:
            print("   → --yes flag set: deleting existing chunks.")
            confirmed = True
        else:
            try:
                answer = input("   → Delete and re-embed? (y/n): ").strip().lower()
                confirmed = answer in ("y", "yes")
            except EOFError:
                print("   → Non-interactive mode: aborting. Use --yes to auto-confirm.")
                sys.exit(0)

        if confirmed:
            col.delete_many({"source_file": pdf_path})
            print(f"   🗑️  Deleted {existing} existing chunks.")
        else:
            print("   → Aborting. Existing data kept.")
            sys.exit(0)

    # ── Step 1: Initialize DB indexes ─────────────────
    print("\n1. Initializing MongoDB...")
    init_db()

    # ── Step 2: Load PDF ───────────────────────────────
    print(f"\n2. Loading PDF: {pdf_path}")
    pages = load_pdf(pdf_path)

    # ── Step 3: Chunk ──────────────────────────────────
    print(f"\n3. Chunking {len(pages)} pages...")
    chunks = chunk_pages(pages, source_file=pdf_path)

    before = len(chunks)
    chunks = [c for c in chunks if len(c.text) >= MIN_CHUNK_CHARS]
    removed = before - len(chunks)
    if removed:
        print(f"   🗑️  Removed {removed} chunks under {MIN_CHUNK_CHARS} chars.")
    print(f"   → {len(chunks)} chunks ready for embedding.")

    # ── Step 4: Embed ──────────────────────────────────
    print(f"\n4. Embedding {len(chunks)} chunks "
          f"(model: {settings.EMBEDDING_MODEL_NAME})...")
    print("   This may take a few minutes...\n")

    start = time.time()
    docs = embed_chunks(chunks)
    elapsed = time.time() - start

    print(f"   ⏱️  Embedding took {elapsed:.1f}s "
          f"({elapsed/len(docs):.2f}s per chunk)")

    # ── Step 5: Save to MongoDB ────────────────────────
    print(f"\n5. Saving {len(docs)} documents to MongoDB...")

    records = [doc.model_dump(by_alias=True, exclude={"id"}) for doc in docs]
    result = col.insert_many(records)

    print(f"   ✅ Inserted {len(result.inserted_ids)} documents.")

    print("\n" + "=" * 55)
    print(f"  ✅ Pipeline complete!")
    print(f"  → {len(docs)} chunks embedded and stored in MongoDB")
    print(f"  → Collection : {settings.MONGO_DB_NAME}.{settings.MONGO_COLLECTION_CHUNKS}")
    print(f"  → Open http://localhost:8081 to browse the data")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG ingestion pipeline — PDF → MongoDB")
    parser.add_argument(
        "--file",
        required=True,
        help="Path to the PDF file to ingest",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Auto-confirm deletion of existing chunks (non-interactive mode)",
    )
    args = parser.parse_args()
    run_pipeline(pdf_path=args.file, auto_confirm=args.yes)