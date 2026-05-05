"""
api/routes/ingest.py
====================
POST /ingest — upload a PDF and run the full ingestion + embedding pipeline.
"""

import os
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from ingestion.loader import load_pdf
from ingestion.chunker import chunk_pages
from embedding.embedder import embed_chunks
from shared.database import get_collection

router = APIRouter()

MIN_CHUNK_CHARS = 50


class IngestResponse(BaseModel):
    filename: str
    pages_loaded: int
    chunks_created: int
    chunks_embedded: int


@router.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            pages = load_pdf(tmp_path)
        except (FileNotFoundError, RuntimeError) as e:
            raise HTTPException(status_code=422, detail=str(e))

        chunks = chunk_pages(pages, source_file=file.filename)
        chunks = [c for c in chunks if len(c.text) >= MIN_CHUNK_CHARS]

        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="No usable text could be extracted from this PDF.",
            )

        try:
            docs = embed_chunks(chunks)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=f"Embedding failed: {e}")

        col = get_collection()
        records = [doc.model_dump(by_alias=True, exclude={"id"}) for doc in docs]
        col.insert_many(records)

        return IngestResponse(
            filename=file.filename,
            pages_loaded=len(pages),
            chunks_created=len(chunks),
            chunks_embedded=len(docs),
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
