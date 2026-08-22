import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CONVERSATIONS_DIR = DATA_DIR / "conversations"
DOCUMENTS_DIR = DATA_DIR / "documents"
MEMORY_DB_PATH = DATA_DIR / "memory" / "studyagent.db"
PERMISSIONS_PATH = PROJECT_ROOT / "config" / "permissions.json"

load_dotenv(PROJECT_ROOT / "backend" / ".env")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
TEXT_MODEL = os.getenv("STUDY_TEXT_MODEL", "llama3.1")
VISION_MODEL = os.getenv("STUDY_VISION_MODEL", "qwen2.5vl:7b")

for _dir in (DATA_DIR, CONVERSATIONS_DIR, DOCUMENTS_DIR, MEMORY_DB_PATH.parent):
    _dir.mkdir(parents=True, exist_ok=True)
