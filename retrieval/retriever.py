"""
retrieval/retriever.py
======================
Loads embedded chunks from MongoDB, ranks them by cosine similarity
to the user's query embedding, and returns the top-k results as
RetrievedChunk objects (the shared contract type).
"""

from shared.config import get_settings
from shared.database import get_collection
from shared.schemas import RetrievedChunk, ChunkMetadata
from embedding.ollama_client import get_embedding
from retrieval.similarity import cosine_similarity


def retrieve(question: str, top_k: int | None = None, doc_type_filter: str | None = None) -> list[RetrievedChunk]:
    """
    End-to-end retrieval: embed the question, fetch candidate vectors
    from MongoDB, score them, and return the top-k chunks.

    Args:
        question:        the user's natural-language question
        top_k:           number of results to return (default from config)
        doc_type_filter: optional doc_type to restrict search scope

    Returns:
        list[RetrievedChunk] sorted by descending similarity score
    """
    settings = get_settings()
    top_k = top_k or settings.DEFAULT_TOP_K

    # 1. Embed the question using the same model as the documents
    query_vec = get_embedding(question)

    # 2. Load candidate chunks from MongoDB
    col = get_collection()
    mongo_filter: dict = {"embedding": {"$exists": True, "$ne": None}}
    if doc_type_filter:
        mongo_filter["metadata.doc_type"] = doc_type_filter

    projection = {
        "_id": 1,
        "text": 1,
        "source_file": 1,
        "metadata": 1,
        "embedding": 1,
    }

    docs = list(col.find(mongo_filter, projection))

    if not docs:
        return []

    # 3. Extract vectors and compute cosine similarity
    doc_vecs = [d["embedding"] for d in docs]
    scores = cosine_similarity(query_vec, doc_vecs)

    # 4. Pair each doc with its score and sort descending
    scored = list(zip(docs, scores))
    scored.sort(key=lambda x: x[1], reverse=True)

    # 5. Apply similarity threshold
    threshold = settings.SIMILARITY_THRESHOLD
    if threshold > 0:
        scored = [(d, s) for d, s in scored if s >= threshold]

    # 6. Take top-k and build RetrievedChunk objects
    results: list[RetrievedChunk] = []
    for doc, score in scored[:top_k]:
        results.append(
            RetrievedChunk(
                chunk_id=str(doc["_id"]),
                text=doc["text"],
                score=round(float(score), 4),
                source_file=doc["source_file"],
                metadata=ChunkMetadata(**doc["metadata"]),
            )
        )

    return results
