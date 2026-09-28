"""FastAPI backend for Agentic RAG Bot."""

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import agent, config, db, vectorstore
from .parsing import chunk_plain_pages, chunk_turns, parse_pdf_bytes

app = FastAPI(title="Agentic RAG Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    session_id: str
    question: str


class SessionCreate(BaseModel):
    title: str = "New session"


class SessionRename(BaseModel):
    title: str


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "user": "admin",
        "vector_store": vectorstore.collection_stats(),
        "answer_model": config.ANSWER_MODEL,
        "grader_model": config.GRADER_MODEL,
    }


@app.get("/api/presets")
def presets():
    return {"questions": config.PRESET_QUESTIONS}


@app.post("/api/sessions")
def create_session(body: SessionCreate):
    return db.create_session(username="admin", title=body.title)


@app.get("/api/sessions")
def list_sessions():
    return db.list_sessions(username="admin")


@app.patch("/api/sessions/{session_id}")
def rename_session(session_id: str, body: SessionRename):
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Empty title")
    db.rename_session(session_id, title[:80])
    return {"ok": True}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    vectorstore.delete_session_data(session_id)  # no-op if nothing was uploaded
    db.delete_session(session_id)
    return {"ok": True}


@app.get("/api/sessions/{session_id}/messages")
def get_messages(session_id: str):
    return db.get_messages(session_id)


@app.get("/api/sessions/{session_id}/files")
def list_files(session_id: str):
    return db.list_session_files(session_id)


@app.post("/api/sessions/{session_id}/files")
async def upload_file(session_id: str, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (25MB max)")

    display_name = file.filename
    try:
        turns = parse_pdf_bytes(data)
        chunks = chunk_turns(turns, display_name) if turns else []
        if not chunks:
            # not a speaker-labeled transcript - fall back to plain page chunking
            chunks = chunk_plain_pages(data, display_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse PDF: {e}")

    if not chunks:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF")

    n = vectorstore.index_chunks(chunks, session_id=session_id)
    record = db.add_session_file(session_id, display_name, n)
    return record


@app.post("/api/ask")
def ask(body: AskRequest):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Empty question")

    db.add_message(body.session_id, "user", question)
    # first question becomes the session title
    if len(db.get_messages(body.session_id)) == 1:
        db.rename_session(body.session_id, question[:60])

    try:
        result = agent.ask(question, session_id=body.session_id)
    except Exception as e:  # surface agent errors to the UI
        raise HTTPException(status_code=500, detail=str(e))

    message_id = db.add_message(
        body.session_id,
        "assistant",
        result["answer"],
        covered=result["covered"],
        trace=result["trace"],
        citations=result["citations"],
    )
    return {"message_id": message_id, **result}
