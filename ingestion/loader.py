"""
ingestion/loader.py
===================
Opens a PDF file and extracts raw text, page by page.
Returns a list of (page_number, text) tuples — one per page.

Uses pdfplumber (better spacing than pypdf for complex PDFs).
"""

import pdfplumber


def load_pdf(file_path: str) -> list[tuple[int, str]]:
    """
    Extract text from a PDF, page by page.

    Args:
        file_path: path to the PDF file

    Returns:
        list of (page_number, text) tuples — page_number starts at 1

    Raises:
        FileNotFoundError: if the PDF doesn't exist at the given path
        RuntimeError: if the PDF has no extractable text (scanned image PDF)
    """
    try:
        pdf = pdfplumber.open(file_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"PDF not found: {file_path}")

    pages = []
    with pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()

            if not text or not text.strip():
                print(f"   ⚠️  Page {i} has no extractable text — skipping.")
                continue

            text = _clean_text(text)
            pages.append((i, text))

    if not pages:
        raise RuntimeError(
            f"No text could be extracted from {file_path}. "
            "This may be a scanned PDF (image-only). "
            "OCR support is not included in this version."
        )

    total_chars = sum(len(t) for _, t in pages)
    print(f"   ✅ Loaded {len(pages)} pages — {total_chars:,} total characters.")
    return pages


def _clean_text(text: str) -> str:
    """
    Light cleanup of raw PDF text.
    - Collapse 3+ consecutive newlines into 2 (preserve paragraph breaks)
    - Strip leading/trailing whitespace per line
    """
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(lines)

    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")

    return cleaned.strip()