"""
Takes a ChunkInput (text + metadata, no vector yet)
Returns a ChunkDocument (same thing + embedding filled in)

This is the only file that combines:
  - the Pydantic types from shared/schemas.py
  - the Ollama call from ollama_client.py
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from shared.schemas import ChunkInput, ChunkDocument
from shared.config import get_settings
from embedding.ollama_client import get_embedding

_print_lock = threading.Lock()


def embed_chunk(chunk: ChunkInput) -> ChunkDocument:
    settings = get_settings()
    vector = get_embedding(chunk.text)
    return ChunkDocument(
        source_file=chunk.source_file,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        char_count=len(chunk.text),
        metadata=chunk.metadata,
        embedding=vector,
        embedding_model=settings.EMBEDDING_MODEL_NAME,
        embedded_at=datetime.now(timezone.utc),
    )


def embed_chunks(chunks: list[ChunkInput]) -> list[ChunkDocument]:
    settings = get_settings()
    total = len(chunks)
    results: list[ChunkDocument | None] = [None] * total
    completed_count = 0
    max_workers = min(settings.EMBEDDING_BATCH_SIZE, total, 8)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(embed_chunk, chunk): i
            for i, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            i = futures[future]
            results[i] = future.result()
            completed_count += 1
            with _print_lock:
                print(
                    f"   Embedding chunk {completed_count}/{total} "
                    f"(chars: {len(chunks[i].text)}) ...",
                    end="\r",
                )

    print(f"\n   Embedded {total} chunks successfully.")
    return [r for r in results if r is not None]