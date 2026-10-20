"""
Central configuration for the Meeting Intelligence backend.
All values are overridable via environment variables so the same code
runs in local dev, CI, and production without changes.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Storage ---------------------------------------------------------------
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'meeting_intel.db'}")

# --- LLM (Anthropic) ---------------------------------------------------------
# Used for: meeting summary, decision/action/risk/question extraction.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# --- Speech-to-Text ----------------------------------------------------------
# TRANSCRIPTION_BACKEND options:
#   "openai_whisper_api" -> calls OpenAI's hosted Whisper endpoint (needs OPENAI_API_KEY)
#   "local_whisper"      -> uses the `openai-whisper` / `faster-whisper` python package locally
#   "mock"                -> deterministic placeholder transcript, used for demos/offline dev
TRANSCRIPTION_BACKEND = os.getenv("TRANSCRIPTION_BACKEND", "mock")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")

# --- Misc ---------------------------------------------------------------------
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))
ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac"}
