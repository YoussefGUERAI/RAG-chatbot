"""
shared/database.py
==================
MongoDB connection — import `get_collection()` anywhere you need DB access.
Indexes are created automatically on first call to `init_db()`.
"""

from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from shared.config import get_settings

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = MongoClient(settings.MONGO_URI)
    return _client


def get_collection() -> Collection:
    settings = get_settings()
    return get_client()[settings.MONGO_DB_NAME][settings.MONGO_COLLECTION_CHUNKS]


def init_db() -> None:
    """
    Call once at application startup (in main.py lifespan).
    Creates the indexes the retrieval step depends on.
    """
    col = get_collection()

    # Dev A needs these for filtering during ingestion
    col.create_index([("source_file", ASCENDING)], name="idx_source_file")
    col.create_index([("metadata.doc_type", ASCENDING)], name="idx_doc_type")

    # Dev B needs this to quickly fetch un-embedded chunks
    col.create_index(
        [("embedded_at", ASCENDING)],
        name="idx_embedded_at",
        sparse=True   # only indexes docs where the field exists
    )

    # Compound index for retrieval pre-filtering (doc_type + embedding existence)
    col.create_index(
        [("metadata.doc_type", ASCENDING), ("embedding", ASCENDING)],
        name="idx_doctype_embedding"
    )

    print("✅ MongoDB indexes initialized.")


def close_db() -> None:
    global _client
    if _client:
        _client.close()
        _client = None
