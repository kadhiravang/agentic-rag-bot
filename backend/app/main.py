"""FastAPI backend for the Executive Oracle."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import agent, config, db, vectorstore

app = FastAPI(title="Executive Oracle API")

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


@app.get("/api/sessions/{session_id}/messages")
def get_messages(session_id: str):
    return db.get_messages(session_id)


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
        result = agent.ask(question)
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
