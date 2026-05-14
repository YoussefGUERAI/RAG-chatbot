"""
generation/prompt.py
====================
Builds the final prompt string from retrieved chunks + user question.
Keeps prompt engineering in one place — easy to iterate on.
"""

from shared.schemas import RetrievedChunk, ConversationTurn


def build_prompt(
    question: str,
    chunks: list[RetrievedChunk],
    history: list[ConversationTurn] | None = None,
) -> str:
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

    history_block = ""
    if history:
        turns = []
        for turn in history:
            turns.append(f"User: {turn.question}\nAssistant: {turn.answer}")
        history_block = (
            "--- CONVERSATION SO FAR ---\n"
            + "\n\n".join(turns)
            + "\n--- END CONVERSATION ---\n\n"
        )

    prompt = (
        "You are a helpful assistant that answers questions based on the provided documentation.\n"
        "Use ONLY the context below to answer. If the context does not contain the answer, say "
        "\"I don't have enough information to answer that.\"\n"
        "Provide a thorough, detailed answer that draws on all relevant context. "
        "When the context describes steps, list them. When it mentions specific buttons, fields, "
        "roles, or screens, name them. Paraphrase or quote specific details rather than summarizing vaguely. "
        "Stay accurate to the source — do not invent information beyond the context.\n"
        "Use the conversation so far only to resolve pronouns and follow-up references — "
        "do not treat it as a source of factual content.\n\n"
        f"{history_block}"
        "--- CONTEXT ---\n"
        f"{context}\n"
        "--- END CONTEXT ---\n\n"
        f"Question: {question}\n"
        "Answer:"
    )

    return prompt
