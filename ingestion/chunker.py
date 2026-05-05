"""
ingestion/chunker.py
====================
Splits pages of text into overlapping chunks using a sentence-aware strategy.

Strategy:
  - Split text into sentences first (never cut mid-sentence)
  - Group sentences until the chunk reaches CHUNK_SIZE characters
  - Start next chunk from CHUNK_OVERLAP characters back (overlap)
  - Track which page each chunk originated from
"""

import re
from shared.schemas import ChunkInput, ChunkMetadata
from shared.config import get_settings


def chunk_pages(pages: list[tuple[int, str]], source_file: str) -> list[ChunkInput]:
    settings = get_settings()
    chunks: list[ChunkInput] = []
    chunk_index = 0

    for page_number, page_text in pages:
        sentences = _split_into_sentences(page_text)
        page_chunks = _group_sentences_into_chunks(
            sentences=sentences,
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )

        for chunk_text in page_chunks:
            if not chunk_text.strip():
                continue

            chunks.append(
                ChunkInput(
                    text=chunk_text.strip(),
                    source_file=source_file,
                    chunk_index=chunk_index,
                    metadata=ChunkMetadata(
                        doc_type="pdf",
                        page_number=page_number,
                        section_title=_detect_section_title(chunk_text),
                    ),
                )
            )
            chunk_index += 1

    print(f"   ✅ Created {len(chunks)} chunks from {len(pages)} pages.")
    return chunks


def _split_into_sentences(text: str) -> list[str]:
    raw = re.split(r'(?<=[.!?])\s+(?=[A-Z])|(?<=\n)\n', text)
    return [s.strip() for s in raw if s.strip()]


def _group_sentences_into_chunks(
    sentences: list[str],
    chunk_size: int,
    overlap: int,
) -> list[str]:
    chunks = []
    current_chars = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        if current_len + sentence_len > chunk_size and current_chars:
            chunk_text = " ".join(current_chars)
            chunks.append(chunk_text)

            overlap_chars = []
            overlap_len = 0
            for prev_sentence in reversed(current_chars):
                sep = 1 if overlap_chars else 0
                if overlap_len + sep + len(prev_sentence) > overlap:
                    break
                overlap_chars.append(prev_sentence)
                overlap_len += sep + len(prev_sentence)

            overlap_chars.reverse()
            current_chars = overlap_chars
            current_len = overlap_len

        current_chars.append(sentence)
        current_len += sentence_len

    if current_chars:
        chunks.append(" ".join(current_chars))

    return chunks


def _detect_section_title(text: str) -> str | None:
    first_line = text.split("\n")[0].strip()
    if not first_line or len(first_line) > 80:
        return None
    is_title_case = first_line.istitle()
    is_all_caps = first_line.isupper()
    no_end_punct = first_line[-1] not in ".!?,"
    if (is_title_case or is_all_caps) and no_end_punct:
        return first_line
    return None