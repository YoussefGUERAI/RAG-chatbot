"""
tests/test_ingestion.py
=======================
Pytest suite for the ingestion pipeline (loader + chunker).

Run with:
    pytest tests/test_ingestion.py -v

For manual inspection:
    python tests/test_ingestion.py
"""

import os
import sys
import pytest
from ingestion.loader import load_pdf
from ingestion.chunker import chunk_pages
from shared.config import get_settings

PDF_PATH = "DocCerts - Documentation.pdf"


@pytest.fixture(scope="module")
def loaded_pages():
    if not os.path.exists(PDF_PATH):
        pytest.skip(f"Test PDF not found: {PDF_PATH}")
    return load_pdf(PDF_PATH)


def test_loader_returns_pages(loaded_pages):
    assert len(loaded_pages) > 0, "PDF should have at least one extractable page"


def test_loader_page_format(loaded_pages):
    for page in loaded_pages:
        assert isinstance(page, tuple) and len(page) == 2, "Each page must be a (int, str) tuple"
        page_num, text = page
        assert isinstance(page_num, int) and page_num >= 1, "Page number must be a positive int"
        assert isinstance(text, str) and len(text) > 0, "Page text must be a non-empty string"


def test_loader_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        load_pdf("nonexistent_file_xyz.pdf")


def test_chunker_produces_chunks(loaded_pages):
    chunks = chunk_pages(loaded_pages, source_file=PDF_PATH)
    assert len(chunks) > 0, "Chunker should produce at least one chunk"


def test_chunker_chunk_content(loaded_pages):
    chunks = chunk_pages(loaded_pages, source_file=PDF_PATH)
    settings = get_settings()
    for chunk in chunks:
        assert len(chunk.text) > 0, "Chunk text must not be empty"
        assert len(chunk.text) <= settings.CHUNK_SIZE * 2, (
            f"Chunk too large: {len(chunk.text)} chars (CHUNK_SIZE={settings.CHUNK_SIZE})"
        )


def test_chunker_metadata(loaded_pages):
    chunks = chunk_pages(loaded_pages, source_file=PDF_PATH)
    for chunk in chunks:
        assert chunk.source_file == PDF_PATH
        assert chunk.chunk_index >= 0
        assert chunk.metadata.doc_type == "pdf"
        assert chunk.metadata.page_number is not None
        assert chunk.metadata.page_number >= 1


def test_chunker_indices_sequential(loaded_pages):
    chunks = chunk_pages(loaded_pages, source_file=PDF_PATH)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks))), "Chunk indices must be sequential starting at 0"


if __name__ == "__main__":
    if not os.path.exists(PDF_PATH):
        print(f"❌ PDF not found: {PDF_PATH}")
        sys.exit(1)

    settings = get_settings()
    print("=" * 50)
    print("  Ingestion pipeline — manual test")
    print("=" * 50)

    pages = load_pdf(PDF_PATH)
    print(f"   → Pages : {len(pages)}")
    print(f"   → Preview: {pages[0][1][:200]!r}")

    chunks = chunk_pages(pages, source_file=PDF_PATH)
    char_counts = [len(c.text) for c in chunks]
    print(f"\n   → Chunks : {len(chunks)}")
    print(f"   → Size settings : {settings.CHUNK_SIZE} chars / {settings.CHUNK_OVERLAP} overlap")
    if char_counts:
        print(f"   → min/max/avg : {min(char_counts)}/{max(char_counts)}/{sum(char_counts)//len(char_counts)}")

    print("\n" + "=" * 50)
    print(f"  ✅ Done — {len(chunks)} chunks ready to embed")
    print("=" * 50)
