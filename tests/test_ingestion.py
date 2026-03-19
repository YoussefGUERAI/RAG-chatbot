"""
test_ingestion.py
=================
Run this to verify loader.py and chunker.py work on your PDF.

Usage (from the rag_contract/ root):
    python test_ingestion.py
"""

from ingestion.loader import load_pdf
from ingestion.chunker import chunk_pages
from shared.config import get_settings

PDF_PATH = "DocCerts - Documentation.pdf"

settings = get_settings()


def test_loader():
    print("1. Testing PDF loader...")
    pages = load_pdf(PDF_PATH)
    print(f"   → Total pages extracted : {len(pages)}")
    print(f"   → First page preview    : {pages[0][1][:200]!r}")
    return pages


def test_chunker(pages):
    print("\n2. Testing chunker...")
    chunks = chunk_pages(pages, source_file=PDF_PATH)

    print(f"   → Total chunks created  : {len(chunks)}")
    print(f"   → Chunk size setting    : {settings.CHUNK_SIZE} chars")
    print(f"   → Overlap setting       : {settings.CHUNK_OVERLAP} chars")

    print("\n   First 3 chunks:")
    for i, chunk in enumerate(chunks[:3]):
        print(f"\n   ── Chunk {i} (page {chunk.metadata.page_number}) ──")
        print(f"   chars       : {len(chunk.text)}")
        print(f"   section     : {chunk.metadata.section_title}")
        print(f"   preview     : {chunk.text[:150]!r}")

    char_counts = [len(c.text) for c in chunks]
    print(f"\n   Chunk size stats:")
    print(f"   → min  : {min(char_counts)} chars")
    print(f"   → max  : {max(char_counts)} chars")
    print(f"   → avg  : {sum(char_counts) // len(char_counts)} chars")

    return chunks


if __name__ == "__main__":
    print("=" * 50)
    print("  Ingestion pipeline — test suite")
    print("=" * 50)

    pages = test_loader()
    chunks = test_chunker(pages)

    print("\n" + "=" * 50)
    print(f"  ✅ Pipeline ready — {len(chunks)} chunks to embed")
    print("=" * 50)