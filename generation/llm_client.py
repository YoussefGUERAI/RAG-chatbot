"""
generation/llm_client.py
========================
Thin wrapper around the Ollama /api/generate endpoint.
Single responsibility: send a prompt string, get back the LLM's text.
"""

import httpx
from shared.config import get_settings


def generate(prompt: str) -> str:
    """
    Send a fully-built prompt to Ollama and return the generated text.

    Args:
        prompt: the complete prompt (system context + retrieved chunks + question)

    Returns:
        str — the LLM's response text

    Raises:
        RuntimeError: if Ollama is unreachable or returns an error
    """
    settings = get_settings()

    try:
        response = httpx.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.LLM_MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": settings.LLM_MAX_TOKENS,
                    "temperature": settings.LLM_TEMPERATURE,
                },
            },
            timeout=600.0,  # LLM generation can be slow on CPU
        )
        response.raise_for_status()

    except httpx.ConnectError:
        raise RuntimeError(
            f"Cannot reach Ollama at {settings.OLLAMA_BASE_URL}. "
            "Make sure `ollama serve` is running."
        )
    except httpx.TimeoutException:
        raise RuntimeError(
            f"Ollama LLM request timed out at {settings.OLLAMA_BASE_URL}. "
            "Try increasing LLM_MAX_TOKENS or check model availability."
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Ollama returned an error: {e.response.text[:500]}")

    data = response.json()

    if "response" not in data:
        raise RuntimeError(
            f"Unexpected Ollama response — 'response' key missing: {data}"
        )

    answer = data["response"].strip()
    if not answer:
        raise RuntimeError("LLM returned an empty response.")
    return answer
