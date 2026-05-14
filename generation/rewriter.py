"""
generation/rewriter.py
======================
Given a follow-up question + conversation history, produce a standalone
search query for the retriever. Resolves pronouns ("that", "it", "they")
and references ("the same thing") into explicit terms.

The user-facing question is never rewritten — only the retrieval query is.
"""

import re
import httpx
from shared.config import get_settings
from shared.schemas import ConversationTurn


_PRONOUN_RE = re.compile(
    r"\b(it|its|that|this|these|those|they|them|their|the same|the other|"
    r"compare|also|too|as well|and what|and how|what about|how about)\b",
    re.IGNORECASE,
)


def looks_like_followup(question: str) -> bool:
    """Cheap heuristic: skip rewriting when the question is clearly self-contained."""
    if len(question) < 60:
        return True
    return bool(_PRONOUN_RE.search(question))


def rewrite_query(question: str, history: list[ConversationTurn]) -> str:
    """
    Ask the LLM to turn a follow-up into a standalone search query.
    Falls back to the original question on any error.
    """
    if not history:
        return question

    settings = get_settings()

    turns = "\n".join(
        f"User: {t.question}\nAssistant: {t.answer[:150]}" for t in history
    )
    prompt = (
        "Rewrite the user's latest question as a single, standalone search query "
        "for a documentation search engine. Resolve pronouns (it, that, they) into the "
        "entity they refer to. The rewritten query should mention ONLY the entity asked "
        "about in the latest question — do not combine entities from prior turns. "
        "Output ONLY the rewritten query — no preamble, no quotes, no explanation.\n"
        "\n"
        "Example 1:\n"
        "Conversation:\n"
        "User: How do I issue a certificate?\n"
        "Assistant: Click 'Create Certificate', choose a blockchain type, then fill in the signers.\n"
        "Latest question: And how do I delete one?\n"
        "Rewritten query: How do I delete a certificate?\n"
        "\n"
        "Example 2:\n"
        "Conversation:\n"
        "User: What can a verifier do?\n"
        "Assistant: A verifier can verify documents and accept or reject verification requests.\n"
        "Latest question: And what about the issuer?\n"
        "Rewritten query: What can an issuer do?\n"
        "\n"
        "Example 3:\n"
        "Conversation:\n"
        "User: What is a Super Admin?\n"
        "Assistant: A Super Admin manages users, organizations, and platform-wide settings.\n"
        "Latest question: How is that different from a regular admin?\n"
        "Rewritten query: How does a Super Admin differ from a regular admin?\n"
        "\n"
        "Now do this one:\n"
        "Conversation:\n"
        f"{turns}\n"
        f"Latest question: {question}\n"
        "Rewritten query:"
    )

    try:
        response = httpx.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.LLM_MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 60, "temperature": 0.0},
            },
            timeout=120.0,
        )
        response.raise_for_status()
        rewritten = response.json().get("response", "").strip()
    except Exception as e:
        print(f"[rewriter] FAILED ({type(e).__name__}): {e} — falling back to original")
        return question

    print(f"[rewriter] raw model output: {rewritten!r}")
    rewritten = rewritten.strip().strip('"').strip("'").splitlines()[0] if rewritten else ""
    if not rewritten or len(rewritten) > 300:
        print(f"[rewriter] guard rejected output, falling back to original")
        return question
    print(f"[rewriter] final rewritten query: {rewritten!r}")
    return rewritten
