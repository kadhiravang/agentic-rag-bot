import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")

TRANSCRIPTS_DIR = PROJECT_DIR / "transcripts"
QDRANT_PATH = str(BACKEND_DIR / "qdrant_data")
SQLITE_PATH = str(BACKEND_DIR / "oracle.db")

COLLECTION = "executive_house_transcripts"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

ANSWER_MODEL = os.getenv("ANSWER_MODEL", "gemini-2.5-flash")
GRADER_MODEL = os.getenv("GRADER_MODEL", "gemini-2.5-flash-lite")

TOP_K = 8          # total; retrieval is balanced across transcripts
PER_SOURCE_K = 4   # top-k fetched from each transcript
MAX_RETRIEVAL_RETRIES = 1

SOURCE_NAMES = [
    "Eventbrite (Julia & Kevin Hartz)",
    "QED Investors / Capital One (Nigel Morris)",
]

PRESET_QUESTIONS = [
    "What's one piece of advice this executive gives about running a business?",
    "What challenge, mistake, or setback do they mention facing?",
    "What's a turning point or unexpected moment they mention in their career?",
]
