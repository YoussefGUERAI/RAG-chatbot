"""
generation/prompt.py
====================
Builds the final prompt string from retrieved chunks + user question.
Keeps prompt engineering in one place — easy to iterate on.
"""

from shared.schemas import RetrievedChunk


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    """
    Assemble the prompt sent to the LLM.

    Structure:
        1. System instruction (role, rules)
        2. Retrieved context blocks
        3. User question

    Args:
        question: the user's original question
        chunks:   top-k RetrievedChunk objects from the retriever

    Returns:
        str — the complete prompt ready for the LLM
    """
    context_blocks = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.source_file
        page = chunk.metadata.page_number
        loc = f"{source} (page {page})" if page else source
        context_blocks.append(f"[{i}] {loc}\n{chunk.text}")

    context = "\n\n".join(context_blocks)

    prompt = (
        "You are a helpful assistant that answers questions based on the provided documentation.\n"
        "Use ONLY the context below to answer. If the context does not contain the answer, say "
        "\"I don't have enough information to answer that.\"\n"
        "Be concise and accurate.\n\n"
        "--- CONTEXT ---\n"
        f"{context}\n"
        "--- END CONTEXT ---\n\n"
        f"Question: {question}\n"
        "Answer:"
    )

    return prompt
