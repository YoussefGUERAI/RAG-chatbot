"""
Takes a ChunkInput (text + metadata, no vector yet)
Returns a ChunkDocument (same thing + embedding filled in)

This is the only file that combines:
  - the Pydantic types from shared/schemas.py
  - the Ollama call from ollama_client.py
"""

from datetime import datetime, timezone
from shared.schemas import ChunkInput, ChunkDocument
from shared.config import get_settings
from embedding.ollama_client import get_embedding


def embed_chunk(chunk: ChunkInput) -> ChunkDocument:
    """
    Embed a single chunk.

    Args:
        chunk: a ChunkInput produced by the ingestion pipeline (Dev A's output)

    Returns:
        ChunkDocument with embedding, embedding_model, and embedded_at filled in
    """
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
    """
    Embed a list of chunks one by one, with progress logging.

    Args:
        chunks: list of ChunkInput objects

    Returns:
        list of ChunkDocument objects ready to be saved to MongoDB
    """
    results = []
    total = len(chunks)

    for i, chunk in enumerate(chunks, start=1):
        print(f"   Embedding chunk {i}/{total} "
              f"(chars: {len(chunk.text)}) ...", end="\r")
        doc = embed_chunk(chunk)
        results.append(doc)

    print(f"\n    Embedded {total} chunks successfully.")
    return results