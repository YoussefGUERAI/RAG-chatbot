"""
shared/config.py
================
Single source of truth for all tunable constants.
Change values here — never hardcode them elsewhere.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):

    # ── MongoDB ──────────────────────────────────
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "rag_chatbot"
    MONGO_COLLECTION_CHUNKS: str = "chunks"

    # ── Embedding model (Dev B owns this) ────────
    EMBEDDING_MODEL_NAME: str = "nomic-embed-text"   # Ollama model name
    EMBEDDING_DIM: int = 768                          # must match the model output
    EMBEDDING_BATCH_SIZE: int = 32                    # chunks per embed() call

    # ── Chunking (Dev A owns this) ────────────────
    CHUNK_SIZE: int = 512        # characters per chunk (not tokens)
    CHUNK_OVERLAP: int = 64      # overlap between consecutive chunks

    # ── Retrieval ─────────────────────────────────
    DEFAULT_TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.0   # minimum score to include (0 = disabled)

    # ── LLM (Dev B owns this) ─────────────────────
    LLM_MODEL_NAME: str = "mistral:7b"   # Ollama model tag
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MAX_TOKENS: int = 512
    LLM_TEMPERATURE: float = 0.2

    # ── API ───────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True      # set False in production

    class Config:
        env_file = ".env"        # override any value via .env file
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Import this everywhere: `from shared.config import get_settings`"""
    return Settings()
