# RAG Chatbot — Tuning & Fixes

Summary of issues encountered while bringing the chatbot to a usable state, and
the changes that resolved them. Read top-to-bottom for context; each section is
self-contained.

---

## 1. Empty answers from `/query` (404)

**Symptom.** The first calls to `POST /query` returned
`{"detail":"No relevant chunks found. Is the database populated?"}` even though
MongoDB had 182 chunks loaded.

**Root cause.** Swagger UI pre-fills string fields with the literal value
`"string"`. The request body sent `doc_type_filter: "string"`, which made the
retriever filter for documents whose `doc_type == "string"` — nothing matched.

**Fix.** Operational, not code: either omit `doc_type_filter` from the request
body or send `null`. Documented as a known Swagger-UI papercut.

---

## 2. LLM call timing out (500 / `httpx.ReadTimeout`)

**Symptom.** `POST /query` returned 500 with `httpx.ReadTimeout`. Backtrace
pointed at `generation/llm_client.py` — the request to Ollama exceeded its
300 s ceiling.

**Root cause.** `mistral:7b` running on CPU generated tokens at roughly
5–10 tok/s. Combined with a long retrieved prompt and an uncapped output, a
single answer could take 5+ minutes.

**Fix.** Two-pronged:
- Switched the LLM to a smaller, faster model: `llama3.2:3b` (`.env`).
- Capped output length: `LLM_MAX_TOKENS=256`.
- Later bumped the client timeout to 600 s as a safety net once the rewriter
  was added (more LLM calls per request).

**Files changed.** `.env`, `generation/llm_client.py:39`.

---

## 3. Short, terse answers

**Symptom.** Even after the timeout was resolved, answers were a single
sentence echoing the chunks (e.g. *"Click the verify button to see details."*).

**Root cause.** Two compounding factors:
- The system prompt instructed *"Be concise."* — the model obeyed.
- The source PDF (DocCerts UI walkthrough) is genuinely shallow on some topics
  (e.g. verification mechanics). No prompt tuning can manufacture content the
  source doesn't contain.

**Fix.** Loosened the prompt to explicitly request thorough, detailed answers
with named UI elements, listed steps, and paraphrased specifics — while keeping
the *"only use the provided context"* guardrail. Bumped `top_k` default from 5
to 7 to give the model more raw material on topics the source covers.

**Files changed.** `generation/prompt.py`, `shared/schemas.py` (`top_k` default),
`index.html` (UI default).

---

## 4. No conversation memory — every question stateless

**Symptom.** The backend treated each `/query` as independent. A follow-up like
*"And what about the issuer?"* had no idea what *"that"* referred to. The
client-side History drawer was just a bookmark list of past questions, not a
real conversation.

**Root cause.** By design — the original API was stateless. Multi-turn dialog
requires the prior transcript to be re-sent with each request (LLMs are
stateless; clients carry the context).

**Fix (Option A — client-supplied history).**
- Added `ConversationTurn` schema and `QueryRequest.history: list[ConversationTurn]`
  (max 5 turns enforced server-side).
- `build_prompt` injects a `--- CONVERSATION SO FAR ---` block above the
  retrieved context, with an explicit instruction that history is for pronoun
  resolution only — not a source of factual content.
- Frontend sends the last 3 turns from its local message log on every request.

**Verified with a control test.** Same follow-up question with empty history
interpreted *"that"* as *"a user"* (wrong); with history it correctly resolved
to *"a verifier"* and produced a contrastive answer.

**Files changed.** `shared/schemas.py`, `generation/prompt.py`,
`api/routes/query.py`, `index.html`.

---

## 5. Follow-ups retrieved the wrong chunks

**Symptom.** Even with conversation history wired up, a follow-up like
*"And what about the issuer?"* pulled retrieval chunks dominated by the word
*"issuer"* but missed any verifier context. The model partially compensated
from the history block but its claims were second-hand, not grounded in
freshly-retrieved source pages.

**Root cause.** Retrieval embeds the raw user question. Pronouns
(*"that"*, *"it"*, *"the same"*) carry no semantic anchor — the embedding
model has no way to know *"that"* refers to *"verifier"* from the prior turn.
So the retriever fires on whatever explicit nouns remain in the current
question and ignores everything else.

**Fix (Option C — LLM query rewriting).**
- New `generation/rewriter.py` with `rewrite_query()` and `looks_like_followup()`.
- Before retrieval, if history is non-empty and the question looks like a
  follow-up (pronoun heuristic or short length), call the LLM with a small
  prompt: *"Rewrite this question as a standalone search query."*
- Use the rewritten query for **retrieval only**. The user's original phrasing
  is still what the answer generation prompt sees, so the user's words are
  preserved in the final answer.
- Response now includes `rewritten_query` so the UI can show transparently what
  was actually searched.

**Files changed.** `generation/rewriter.py` (new), `shared/schemas.py`
(`QueryResponse.rewritten_query`), `api/routes/query.py`, `index.html`
(*"Searched as: ..."* note under each assistant bubble).

---

## 6. Rewriter produced muddled queries

**Symptom.** First rewrites from `llama3.2:3b` were imperfect. *"And what
about the issuer?"* with a prior verifier turn became
*"what can an issuer do in a Verifier Organization?"* — vocabulary from the
prior turn bled into the rewrite.

**Root cause.** Zero-shot prompting on a 3B model. Smaller models follow loose
instructions inconsistently when the prompt asks them to combine multiple
signals (resolve a pronoun + drop prior context + keep the question shape).

**Fix.** Few-shot prompting — added 3 worked input/output examples to the
rewriter prompt, plus a tighter instruction (*"mention ONLY the entity asked
about in the latest question — do not combine entities from prior turns"*).
Tightened history truncation from 300 → 150 chars to reduce bleed.

**Verified with the same flow.** Rewrite became *"What can an issuer do?"* —
clean, single-entity, no leaked vocabulary. Source pages landed squarely in the
issuer chapter (20–60) instead of mixing in verifier pages (118–131).

**Files changed.** `generation/rewriter.py`.

---

## 7. UI was Q→A, not a conversation

**Symptom.** Original UI was a two-column layout: input on the left, single
answer on the right. Each new question replaced the previous answer, with
"History" hidden behind a drawer. It didn't reflect the new multi-turn
backend.

**Fix.** Converted to a chat layout:
- Single vertical message feed with user (navy gradient) and assistant
  (light grey, teal accent) bubbles.
- Sticky input bar at the bottom — Enter to send, Shift+Enter for newline.
- Each assistant bubble carries metadata badges (model, latency, source count),
  the *"Searched as: ..."* rewrite note when applicable, and a collapsible
  source list with page numbers and similarity scores.
- "New chat" button clears the feed and resets server-bound history.
- Messages persist to `localStorage` (`rag_messages`) across reloads.
- Auto-scroll to the latest message after each turn.

**Files changed.** `index.html` (CSS additions + render block rewrite).

---

## Final architecture

```
User question (frontend)
         │
         ▼
POST /query  { question, top_k, history, doc_type_filter? }
         │
         ▼
┌────────────────────────────────────────────────────────┐
│ api/routes/query.py                                    │
│                                                        │
│  1. If history present AND question looks like a       │
│     follow-up → call rewrite_query() (Ollama LLM)      │
│  2. retrieve(search_query, top_k) via embeddings       │
│  3. build_prompt(question, chunks, history)            │
│  4. generate(prompt) via Ollama LLM                    │
│  5. Return { answer, retrieved_chunks, rewritten_query,│
│              model_used, latency_ms }                  │
└────────────────────────────────────────────────────────┘
         │
         ▼
Chat UI appends user message + assistant bubble
```

**Two distinct LLM calls per follow-up:**
- Rewriter: short prompt (~600 tokens with few-shot examples), `num_predict=60`,
  `temperature=0.0`, 120 s timeout. Used only for retrieval.
- Generator: full RAG prompt with retrieved chunks + history, `num_predict=256`,
  `temperature=0.2`, 600 s timeout. Produces the user-visible answer.

---

## How to run

```bash
# 1. MongoDB (Docker)
docker compose up -d

# 2. Ollama with both models
ollama serve            # if not already running
ollama pull llama3.2:3b
ollama pull nomic-embed-text

# 3. .env (defaults are fine; override LLM_MODEL_NAME / LLM_MAX_TOKENS as needed)
cp .env.example .env

# 4. Populate the DB (one-time, ~5–10 min on CPU)
python pipeline.py

# 5. API
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 6. Static UI server (separate terminal)
python -m http.server 5173
# Open http://localhost:5173/index.html
```

## Verification flow

1. Ask: *"What can a verifier do?"* — should return verifier content with
   pages in the 118–131 range.
2. Ask: *"And what about the issuer?"* — should return issuer content with
   pages in the 20–60 range, and an italic *"Searched as: 'What can an issuer
   do?'"* line under the answer.
3. Open uvicorn terminal — confirm `[rewriter] final rewritten query: 'What
   can an issuer do?'` appears for the second request.
