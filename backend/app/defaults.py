"""The two known Salvi Executive House transcripts, available to load into any
session on request. Nothing here runs automatically or is shared across
sessions - loading is an explicit per-session action (see main.py)."""

from . import config, vectorstore
from .parsing import chunk_turns, parse_transcript

DEFAULT_TRANSCRIPTS = {
    "Eventbrite Stringout Transcript.docx.pdf": "Eventbrite (Julia & Kevin Hartz)",
    "QED Investors _ Capital One Transcript.docx.pdf": "QED Investors / Capital One (Nigel Morris)",
}


def load_default_transcripts(session_id: str) -> list[dict]:
    """Parse + chunk + index both known transcripts into one session's scope.
    Returns one summary dict per file (used to write session_files rows)."""
    results = []
    for filename, display_name in DEFAULT_TRANSCRIPTS.items():
        path = config.TRANSCRIPTS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing bundled transcript: {path}")
        turns = parse_transcript(path, display_name)
        chunks = chunk_turns(turns, display_name)
        n = vectorstore.index_chunks(chunks, session_id=session_id)
        results.append({"filename": display_name, "chunks": n})
    return results
