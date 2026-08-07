# Executive Oracle — Salvi Round 2 Build Exercise

Grounded Q&A over PDF transcripts, built as an **agentic RAG** pipeline with a fully
**session-scoped knowledge base** — every session starts empty and owns exactly the
documents you add to it, isolated from every other session. Every claim in an answer
is cited (document → speaker → timestamp → page), and questions the loaded documents
don't cover get an honest *"this wasn't covered in the provided transcripts"* instead
of a guess.

For the Salvi assignment specifically: in a session, click **"+ Add PDF"** and
upload the two provided transcripts (`transcripts/Eventbrite Stringout
Transcript.docx.pdf` and `transcripts/QED Investors _ Capital One
Transcript.docx.pdf`), then ask the 3 questions.

## Architecture

```
PDF ──► parser (PyMuPDF) ──► speaker-turn chunks ──► FastEmbed ──► Qdrant (embedded)
  ▲  uploaded per-session, tagged with that session_id — never shared  │
                    "+ Add PDF" (any file, any session)                │
                                                                        │
User ──► React UI ──► FastAPI ──► LangGraph agent ─────────────────────┘
                         │            rewrite → retrieve (session-scoped) ─┬─► answer (cited)
                       SQLite                    ▲                grade ──┼─► retry (1x)
               (users/sessions/files/messages)   └── rewrite ◄────────────┴─► not covered
```

- **Ingestion** — PDFs are parsed into speaker turns (keeping inline `[HH:MM:SS]`
  markers and page numbers), grouped into ~1500-char chunks with overlap, embedded
  locally with FastEmbed (`bge-small-en-v1.5`), and stored in **Qdrant** (embedded
  on-disk mode — same API as server Qdrant). Every point carries a `session_id`
  payload; retrieval is a hard filter on that field, so sessions never see each
  other's documents. A generic (non-speaker-labeled) PDF falls back to plain
  page-based chunking.
- **Agent (LangGraph)** — a small self-corrective graph:
  1. *rewrite*: turn the question into a retrieval query (Claude Haiku)
  2. *retrieve*: top-k semantic search from Qdrant
  3. *grade*: LLM relevance grader drops off-topic chunks (banter, mic checks)
  4. *route*: relevant chunks → answer; none → one rewrite-and-retry; still none →
     grounded refusal
  5. *answer*: Gemini 2.5 Flash answers **only** from surviving chunks, with
     structured output enforcing inline `[n]` citations + verbatim supporting quotes
  (rewrite/grade use Gemini 2.5 Flash-Lite; models configurable in `.env`)
- **Persistence** — SQLite tracks users (admin for now), sessions (renamable,
  deletable), messages, per-answer citations, and per-session files.
- **UI** — React + Vite: a "This session:" sources bar showing exactly what's been
  uploaded (via "+ Add PDF"), the 3 assigned questions as presets, a **References**
  side tab (who said it, timestamp, page, quote, retrieval score) and an **Agent
  trace** tab showing each step the agent took. Sessions can be renamed and
  deleted (which also purges that session's vectors).

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

## The 3 assigned questions

Available as one-click presets in the UI:

1. What's one piece of advice this executive gives about running a business?
2. What challenge, mistake, or setback do they mention facing?
3. What's a turning point or unexpected moment they mention in their career?

Plus free-form questions — including off-topic ones, to demo the refusal path.
