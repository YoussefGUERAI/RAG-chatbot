"""
api/routes/query.py
===================
POST /query — the main RAG endpoint.
Takes a question, retrieves relevant chunks, generates an answer.
"""

import time
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from shared.schemas import QueryRequest, QueryResponse
from shared.config import get_settings
from shared.database import get_collection
from retrieval.retriever import retrieve
from generation.prompt import build_prompt
from generation.llm_client import generate
from generation.rewriter import rewrite_query, looks_like_followup

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """
    Full RAG pipeline in one request:
      1. Retrieve top-k chunks matching the question
      2. Build a prompt from the chunks
      3. Generate an answer via LLM
      4. Return structured response
    """
    start = time.perf_counter()
    settings = get_settings()

    # 0. Rewrite the search query for follow-ups (history only)
    search_query = req.question
    rewritten_query = None
    if req.history and looks_like_followup(req.question):
        rewritten_query = rewrite_query(req.question, req.history)
        if rewritten_query and rewritten_query != req.question:
            search_query = rewritten_query

    # 1. Retrieve
    try:
        chunks = retrieve(
            question=search_query,
            top_k=req.top_k,
            doc_type_filter=req.doc_type_filter,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Retrieval failed: {e}")

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No relevant chunks found. Is the database populated?",
        )

    # 2. Build prompt (with optional conversation history)
    prompt = build_prompt(req.question, chunks, history=req.history)

    # 3. Generate
    try:
        answer = generate(prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"LLM generation failed: {e}")

    elapsed_ms = (time.perf_counter() - start) * 1000

    return QueryResponse(
        question=req.question,
        answer=answer,
        retrieved_chunks=chunks,
        model_used=settings.LLM_MODEL_NAME,
        latency_ms=round(elapsed_ms, 1),
        rewritten_query=rewritten_query if rewritten_query and rewritten_query != req.question else None,
    )


@router.get("/documents")
def list_documents():
    col = get_collection()
    pipeline = [
        {"$group": {
            "_id": "$source_file",
            "chunks": {"$sum": 1},
            "pages": {"$addToSet": "$metadata.page_number"},
        }},
        {"$sort": {"_id": 1}},
    ]
    results = list(col.aggregate(pipeline))

    # Deduplicate by basename — same file ingested from different paths counts once
    seen = {}
    for r in results:
        name = r["_id"].replace("\\", "/").split("/")[-1]
        if name not in seen:
            seen[name] = {"filename": name, "chunks": 0, "pages": set()}
        seen[name]["chunks"] += r["chunks"]
        seen[name]["pages"].update(p for p in r["pages"] if p is not None)

    docs = [
        {"filename": v["filename"], "chunks": v["chunks"], "pages": len(v["pages"])}
        for v in seen.values()
    ]
    return {"documents": docs, "total": len(docs)}


@router.get("/documents/{filename}/download")
def download_document(filename: str):
    col = get_collection()
    doc = col.find_one(
        {"source_file": {"$regex": filename.replace(".", r"\.")}},
        {"source_file": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    path = Path(doc["source_file"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk.")

    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name,
    )
