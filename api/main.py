"""
api/main.py
===========
FastAPI application with lifespan hooks for MongoDB init/cleanup.
Run with:  python -m uvicorn api.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from shared.database import init_db, close_db
from api.routes.query import router as query_router


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

app.include_router(query_router)


@app.get("/health")
def health():
    return {"status": "ok"}
