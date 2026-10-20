"""
Speech-to-Text service layer.

Three interchangeable backends are supported via TRANSCRIPTION_BACKEND:

1. "openai_whisper_api" - calls OpenAI's hosted Whisper transcription
   endpoint (needs network access + OPENAI_API_KEY). Best accuracy,
   zero local setup.

2. "local_whisper" - uses the `faster-whisper` (or `openai-whisper`)
   python package to transcribe on-device. No API key needed, but the
   model weights must be downloaded once (requires internet the first
   time, then works fully offline).

3. "mock" - deterministic offline placeholder used for local dev/demo
   environments with no internet/model access. Lets the rest of the
   pipeline (analysis, dashboard, search) be fully exercised without a
   real ASR engine.

Swapping backends never requires touching any other part of the app -
callers only ever use `transcribe_audio()`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict

from app.config import TRANSCRIPTION_BACKEND, OPENAI_API_KEY, WHISPER_MODEL_SIZE


class TranscriptionResult:
    def __init__(self, full_text: str, segments: List[Dict], language: str, engine: str):
        self.full_text = full_text
        self.segments = segments
        self.language = language
        self.engine = engine


def _mock_transcribe(audio_path: Path) -> TranscriptionResult:
    """
    Deterministic placeholder transcript. In a real deployment this branch
    is never hit (a real backend is configured). It exists so the whole
    upload -> transcribe -> analyze -> search pipeline can be demoed
    without network access to a real ASR provider.
    """
    demo_text = (
        "Project kickoff sync. Priya opened the meeting and reviewed last "
        "sprint's velocity. Ramesh raised a concern that the payments "
        "integration is blocked on the vendor sandbox credentials, which "
        "is a risk to the March 15 release. The team decided to move the "
        "beta launch date to March 22 to absorb that risk. Ananya will "
        "follow up with the vendor and get sandbox access by next Friday. "
        "Kiran agreed to finish the reporting dashboard UI by next "
        "Wednesday. It was decided that all API changes going forward "
        "require a design review before merging. An open question was "
        "raised about whether the mobile app needs offline support in "
        "this release, to be answered by the product team next week. "
        "Suresh will draft the updated rollout plan and share it before "
        "Monday's stakeholder review."
    )
    segments = [{"start": 0.0, "end": 12.0, "speaker": "Speaker 1", "text": demo_text}]
    return TranscriptionResult(demo_text, segments, "en", "mock")


def _openai_whisper_api_transcribe(audio_path: Path) -> TranscriptionResult:
    import requests  # local import so it's optional

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set for openai_whisper_api backend")

    with open(audio_path, "rb") as f:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            files={"file": (audio_path.name, f)},
            data={"model": "whisper-1", "response_format": "verbose_json"},
            timeout=600,
        )
    resp.raise_for_status()
    data = resp.json()
    segments = [
        {
            "start": seg.get("start", 0.0),
            "end": seg.get("end", 0.0),
            "speaker": None,
            "text": seg.get("text", "").strip(),
        }
        for seg in data.get("segments", [])
    ]
    return TranscriptionResult(data.get("text", ""), segments, data.get("language", "en"), "openai_whisper_api")


def _local_whisper_transcribe(audio_path: Path) -> TranscriptionResult:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "local_whisper backend selected but `faster-whisper` is not "
            "installed. Run: pip install faster-whisper"
        ) from e

    model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    segments_iter, info = model.transcribe(str(audio_path))
    segments = []
    full_text_parts = []
    for seg in segments_iter:
        segments.append({"start": seg.start, "end": seg.end, "speaker": None, "text": seg.text.strip()})
        full_text_parts.append(seg.text.strip())
    return TranscriptionResult(
        " ".join(full_text_parts), segments, info.language or "en", f"local_whisper:{WHISPER_MODEL_SIZE}"
    )


_BACKENDS = {
    "mock": _mock_transcribe,
    "openai_whisper_api": _openai_whisper_api_transcribe,
    "local_whisper": _local_whisper_transcribe,
}


def transcribe_audio(audio_path: Path, backend: str | None = None) -> TranscriptionResult:
    backend = backend or TRANSCRIPTION_BACKEND
    fn = _BACKENDS.get(backend)
    if fn is None:
        raise ValueError(f"Unknown TRANSCRIPTION_BACKEND '{backend}'. Options: {list(_BACKENDS)}")
    return fn(audio_path)


def segments_to_json(segments: List[Dict]) -> str:
    return json.dumps(segments)
