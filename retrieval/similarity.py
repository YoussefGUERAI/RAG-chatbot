"""
retrieval/similarity.py
=======================
Pure-math cosine similarity using NumPy.
No database, no Pydantic — just vectors in, scores out.
"""

import numpy as np


def cosine_similarity(query_vec: list[float], doc_vecs: list[list[float]]) -> list[float]:
    """
    Compute cosine similarity between a single query vector and a list of
    document vectors.

    Args:
        query_vec:  1-D list of floats (e.g. 768-dim embedding of user query)
        doc_vecs:   list of 1-D float lists (embeddings from MongoDB)

    Returns:
        list[float] of similarity scores in the same order as doc_vecs,
        each in the range [-1.0, 1.0] (typically 0.0–1.0 for normalized embeddings).
    """
    q = np.array(query_vec, dtype=np.float32)
    D = np.array(doc_vecs, dtype=np.float32)

    # Norms
    q_norm = np.linalg.norm(q)
    d_norms = np.linalg.norm(D, axis=1)

    # Guard against zero-length vectors
    if q_norm == 0:
        return [0.0] * len(doc_vecs)

    # dot(q, each row of D) / (||q|| * ||d_i||)
    scores = D @ q / (q_norm * d_norms + 1e-10)

    return scores.tolist()
