"""
api/main.py
===========
FastAPI application with lifespan hooks for MongoDB init/cleanup.
Run with:  python -m uvicorn api.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.database import init_db, close_db
from api.routes.query import router as query_router
from api.routes.ingest import router as ingest_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    print("🚀 RAG Chatbot API started.")
    yield
    # Shutdown
    close_db()
    print("🛑 RAG Chatbot API stopped.")


app = FastAPI(
    title="RAG Chatbot API",
    description="Ask questions about your documents using retrieval-augmented generation.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router)
app.include_router(ingest_router)


@app.get("/health")
def health():
    return {"status": "ok"}
