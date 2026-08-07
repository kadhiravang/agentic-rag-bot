# Deliverables for Sejal

## Approach bullets (paste into the reply)

- I built **Executive Oracle**, a small web app that answers questions about the two
  Executive House transcripts using **agentic RAG** — every answer is grounded in,
  and cited to, the transcripts themselves.
- **Ingestion**: the PDFs are parsed into speaker turns (keeping the inline
  timestamps and page numbers), chunked, embedded locally with FastEmbed, and stored
  in a **Qdrant** vector database.
- **Agent**: a **LangGraph** graph runs each question through
  *query rewrite → vector retrieval → LLM relevance grading → grounded answer*
  (Gemini 2.5/3.5 Flash). If nothing relevant is retrieved it automatically rewrites
  the query and retries once; if there's still no evidence, it answers
  *"This wasn't covered in the provided transcripts"* instead of guessing.
- **Citations**: structured model output forces every claim to carry an inline `[n]`
  marker tied to the exact chunk — the UI's References panel shows which transcript,
  which speaker, the approximate timestamp, the page, and a verbatim supporting quote.
- **App**: React chat UI (the 3 assigned questions are one-click presets) + FastAPI
  backend, with sessions and per-answer citations persisted in SQLite.
- **Session-scoped knowledge base**: every session starts completely empty and owns
  exactly the PDFs you upload into it — nothing is shared or preloaded across
  sessions, and there's no built-in shortcut for any specific file, including the
  two provided transcripts. You add what you want a session to know about.
- **Why this design**: retrieval keeps answers auditable, the grading step filters
  out the banter/mic-check portions of the transcripts, the refusal path makes the
  "don't guess" requirement a structural guarantee rather than a prompt hint, and
  session-level isolation means this scales past two fixed transcripts into a real
  multi-project tool — closer to what the CEO Oracle project would need.

## Video shot list (~4½ min target, under 5)

Record with Loom / OBS / Win+G Game Bar at 1080p. Have both servers running and a
fresh session open before recording.

1. **Intro (0:00–0:20)** — camera or voiceover: "Hi, I'm Kadhiravan — this is my
   round-2 build: Executive Oracle, a tool that answers the three questions from the
   two Executive House transcripts, with citations, and refuses to guess."
2. **Architecture (0:20–1:00)** — show the README diagram. One sentence per stage:
   parse → chunk → embed (local) → Qdrant (session-scoped); question → LangGraph
   agent (rewrite, retrieve, grade, answer) → cited answer; SQLite for sessions.
3. **New session, upload the transcripts (1:00–1:25)** — click **+ New session**,
   show it's genuinely empty ("This session is empty"), click **+ Add PDFs** and
   select both transcript files at once in the file picker (Ctrl/Shift-click). Say
   in one line: "Every session owns exactly the documents you upload into it —
   nothing's preloaded or shared across sessions; there's no special-casing for
   these two files either."
4. **Question 1 (1:25–2:15)** — click preset 1. While it runs, point at the status
   line ("rewrite → retrieve → grade → answer"). When the answer lands: read a
   sentence, click a citation chip → References panel highlights the source card —
   call out transcript name, speaker, timestamp, page, quote.
5. **Question 2 (2:25–3:00)** — click preset 2. Point out the answer cites BOTH
   transcripts (Nigel's regulator crisis, Julia's "public company psychosis").
6. **Question 3 (3:00–3:35)** — click preset 3. Then open the **Agent trace** tab
   and walk the steps: query rewrite, balanced Qdrant retrieval, grading count,
   grounded answer.
7. **Refusal demo (3:35–4:05)** — type an off-topic question (e.g. "What does this
   executive think about cryptocurrency regulation in Japan?"). Show the ⚠ "Not
   covered in the provided transcripts" response: "Per the brief — when it's not in
   the uploaded documents, the correct output is to say so."
8. **Wrap (4:05–4:40)** — stack recap in one breath (Qdrant, FastEmbed, LangGraph,
   Gemini, FastAPI, SQLite, React) + one forward-looking line: "Because each
   session's knowledge base is fully isolated and built entirely from what you
   upload, this generalizes past two fixed transcripts into a real multi-project
   tool — closer to what the CEO Oracle project would need."

Tips: hide bookmarks bar, 100% zoom, do one silent dry run first so the model
responses are warm and you know the timings.
