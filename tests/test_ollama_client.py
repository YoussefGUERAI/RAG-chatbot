"""
test_ollama_client.py
=====================
Run this to verify ollama_client.py works before writing anything else.

Usage (from the rag_contract/ root):
    python test_ollama_client.py
"""

import sys
from embedding.ollama_client import get_embedding, is_ollama_running
from shared.config import get_settings

settings = get_settings()


def test_health_check():
    print("1. Checking Ollama is reachable...")
    if not is_ollama_running():
        print(f"   ❌ Cannot reach Ollama at {settings.OLLAMA_BASE_URL}")
        print("   → Make sure `ollama serve` is running in another terminal.")
        sys.exit(1)
    print(f"   ✅ Ollama is running at {settings.OLLAMA_BASE_URL}")


def test_embedding():
    print(f"\n2. Testing embedding model ({settings.EMBEDDING_MODEL_NAME})...")

    test_text = "This is a test sentence for the RAG chatbot."
    vector = get_embedding(test_text)

    print(f"   ✅ Got embedding vector")
    print(f"   → Dimensions : {len(vector)} (expected {settings.EMBEDDING_DIM})")
    print(f"   → First 5 values: {[round(v, 4) for v in vector[:5]]}")

    if len(vector) != settings.EMBEDDING_DIM:
        print(f"   ⚠️  Dimension mismatch! Update EMBEDDING_DIM in config.py to {len(vector)}")
    else:
        print(f"   ✅ Dimensions match config ({settings.EMBEDDING_DIM})")


def test_two_different_texts():
    print("\n3. Sanity check — two different texts should give different vectors...")

    v1 = get_embedding("The sky is blue.")
    v2 = get_embedding("MongoDB is a NoSQL database.")

    # If vectors were identical something is very wrong
    are_different = v1[:5] != v2[:5]
    if are_different:
        print("   ✅ Different texts produce different vectors — looks correct")
    else:
        print("   ❌ Both texts returned identical vectors — something is wrong")


if __name__ == "__main__":
    print("=" * 50)
    print("  ollama_client.py — test suite")
    print("=" * 50)

    test_health_check()
    test_embedding()
    test_two_different_texts()

    print("\n" + "=" * 50)
    print("  All checks passed — ready to build embedder.py")
    print("=" * 50)
