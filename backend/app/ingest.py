"""Ingestion pipeline: PDFs -> speaker turns -> chunks -> Qdrant.

Run from backend/:  py -m app.ingest
"""

from . import config, vectorstore
from .parsing import chunk_turns, parse_transcript

# Display names for the source PDFs
SOURCES = {
    "Eventbrite Stringout Transcript.docx.pdf": "Eventbrite (Julia & Kevin Hartz)",
    "QED Investors _ Capital One Transcript.docx.pdf": "QED Investors / Capital One (Nigel Morris)",
}


def run_ingest() -> dict:
    vectorstore.reset_collection()
    summary = {}
    for filename, display_name in SOURCES.items():
        path = config.TRANSCRIPTS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing transcript: {path}")
        turns = parse_transcript(path, display_name)
        chunks = chunk_turns(turns, display_name)
        n = vectorstore.index_chunks(chunks, session_id=config.SHARED_SCOPE)
        summary[display_name] = {"turns": len(turns), "chunks": n}
        print(f"[ingest] {display_name}: {len(turns)} turns -> {n} chunks")
    return summary


if __name__ == "__main__":
    run_ingest()
    print("[ingest] done:", vectorstore.collection_stats())
