import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BACKEND_DIR / ".env")

QDRANT_PATH = str(BACKEND_DIR / "qdrant_data")
SQLITE_PATH = str(BACKEND_DIR / "oracle.db")

COLLECTION = "session_documents"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

ANSWER_MODEL = os.getenv("ANSWER_MODEL", "gemini-3.5-flash")
GRADER_MODEL = os.getenv("GRADER_MODEL", "gemini-3.5-flash-lite")

TOP_K = 8          # total chunks handed to the grader/answerer
PER_SOURCE_K = 4   # cap per distinct source document, so one file can't crowd out another
MAX_RETRIEVAL_RETRIES = 1

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25MB per file

PRESET_QUESTIONS = [
    "What is this document about?",
    "What are the key points or findings?",
    "Are there any risks, limitations, or open questions mentioned?",
]
