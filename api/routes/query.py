"""
api/routes/query.py
===================
POST /query — the main RAG endpoint.
Takes a question, retrieves relevant chunks, generates an answer.
"""

import time
from fastapi import APIRouter, HTTPException
from shared.schemas import QueryRequest, QueryResponse
from shared.config import get_settings
from retrieval.retriever import retrieve
from generation.prompt import build_prompt
from generation.llm_client import generate

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

    # 1. Retrieve
    try:
        chunks = retrieve(
            question=req.question,
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

    # 2. Build prompt
    prompt = build_prompt(req.question, chunks)

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
    )
