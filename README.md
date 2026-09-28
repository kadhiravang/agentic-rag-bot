# Agentic RAG Bot

Grounded Q&A over your own PDFs, built as an **agentic RAG** pipeline with a fully
**session-scoped knowledge base** — every session starts empty and owns exactly the
documents you add to it, isolated from every other session. Every claim in an answer
is cited (document → speaker → timestamp → page, when available), and questions the
loaded documents don't cover get an honest *"this wasn't covered in the provided
documents"* instead of a guess.

Upload any PDF, ask questions about it, and get answers you can actually check —
no hallucinated citations, no leakage between unrelated sessions.

## Architecture

```
PDF ──► parser (PyMuPDF) ──► speaker-turn chunks ──► FastEmbed ──► Qdrant (embedded)
  ▲  uploaded per-session, tagged with that session_id — never shared  │
                    "+ Add PDFs" (any file, any session)               │
                                                                        │
User ──► React UI ──► FastAPI ──► LangGraph agent ─────────────────────┘
                         │            rewrite → retrieve (session-scoped) ─┬─► answer (cited)
                       SQLite                    ▲                grade ──┼─► retry (1x)
               (users/sessions/files/messages)   └── rewrite ◄────────────┴─► not covered
```

- **Ingestion** — PDFs are parsed into speaker turns (keeping inline `[HH:MM:SS]`
  markers and page numbers) when the document is speaker-labeled, grouped into
  ~1500-char chunks with overlap, embedded locally with FastEmbed
  (`bge-small-en-v1.5`), and stored in **Qdrant** (embedded on-disk mode — same
  API as server Qdrant). Every point carries a `session_id` payload; retrieval is
  a hard filter on that field, so sessions never see each other's documents. A
  generic (non-speaker-labeled) PDF falls back to plain page-based chunking.
- **Agent (LangGraph)** — a small self-corrective graph:
  1. *rewrite*: turn the question into a retrieval query
  2. *retrieve*: top-k semantic search from Qdrant, session-scoped
  3. *grade*: LLM relevance grader drops off-topic chunks
  4. *route*: relevant chunks → answer; none → one rewrite-and-retry; still none →
     grounded refusal
  5. *answer*: the model answers **only** from surviving chunks, with structured
     output enforcing inline `[n]` citations + verbatim supporting quotes
  (models configurable in `.env` — defaults to Gemini Flash / Flash-Lite)
- **Persistence** — SQLite tracks users (admin for now), sessions (renamable,
  deletable), messages, per-answer citations, and per-session files.
- **UI** — React + Vite: a "This session:" sources bar showing exactly what's been
  uploaded (via "+ Add PDFs", multi-file), a **References** side tab (who said it,
  timestamp, page, quote, retrieval score) and an **Agent trace** tab showing each
  step the agent took. Sessions can be renamed and deleted (which also purges
  that session's vectors).

## Run it

Backend (Python 3.12):

```
cd backend
py -3.12 -m venv .venv          # once
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # then put your GEMINI_API_KEY in .env (free: aistudio.google.com/apikey)
.venv\Scripts\uvicorn app.main:app --port 8000
```

Frontend:

```
cd frontend
npm install
npm run dev        # http://localhost:5173
```

## Using it

1. Click **+ New session**.
2. Click **+ Add PDFs** and upload one or more of your own documents (multi-select
   works).
3. Ask a question, or click one of the presets. If the answer draws on the
   documents, every claim carries a `[n]` citation you can click to see exactly
   which document, page, and (for transcripts) speaker and timestamp it came from.
4. Ask something the documents don't cover — it'll say so instead of guessing.

## Why this design

Retrieval keeps every answer auditable back to a source line. The grading step
filters out irrelevant chunks before they ever reach the answering model. The
refusal path makes "don't guess" a structural guarantee rather than a prompt hint.
And session-level isolation means this generalizes past a fixed document set into
a real multi-project tool.
