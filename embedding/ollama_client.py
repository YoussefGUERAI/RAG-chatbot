"""
embedding/ollama_client.py
==========================
Thin wrapper around the Ollama HTTP API.
Only two responsibilities:
  1. get_embedding(text)  → list[float]
  2. is_ollama_running()  → bool  (health check)

Nothing else. No MongoDB, no Pydantic, no business logic.
"""

import httpx
from shared.config import get_settings


def get_embedding(text: str) -> list[float]:
    """
    Send a single text string to Ollama, get back a vector.

    Args:
        text: the raw string to embed (one chunk)

    Returns:
        list[float] of length EMBEDDING_DIM (768 for nomic-embed-text)

    Raises:
        RuntimeError: if Ollama is unreachable or returns an error
    """
    settings = get_settings()

    try:
        response = httpx.post(
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={
                "model": settings.EMBEDDING_MODEL_NAME,
                "prompt": text,       # Ollama uses "prompt", not "input"
            },
            timeout=30.0,            # 30s is generous — embedding is fast
        )
        response.raise_for_status()  # raises if HTTP 4xx or 5xx

    except httpx.ConnectError:
        raise RuntimeError(
            f"Cannot reach Ollama at {settings.OLLAMA_BASE_URL}. "
            "Make sure `ollama serve` is running."
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Ollama returned an error: {e.response.text}")

    data = response.json()

    if "embedding" not in data:
        raise RuntimeError(
            f"Unexpected Ollama response — 'embedding' key missing: {data}"
        )

    return data["embedding"]


def is_ollama_running() -> bool:
    """
    Quick health check — call this at startup before doing any work.

    Returns:
        True if Ollama is reachable, False otherwise
    """
    settings = get_settings()
    try:
        response = httpx.get(
            f"{settings.OLLAMA_BASE_URL}",
            timeout=5.0,
        )
        return response.status_code == 200
    except httpx.ConnectError:
        return False
