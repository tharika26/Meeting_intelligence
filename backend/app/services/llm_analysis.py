"""
LLM-powered meeting analysis.

Sends the transcript to Claude with a strict JSON-only prompt and parses
out: summary, key topics, action items (with owner + deadline), decisions,
risks, and open questions.

If ANTHROPIC_API_KEY is not configured, falls back to a lightweight
rule-based extractor so the rest of the app (dashboard, search, action
tracker) remains fully testable offline.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict

from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

SYSTEM_PROMPT = """You are a meeting-intelligence extraction engine. You are \
given a raw meeting transcript. Extract structured information and respond \
with ONLY valid JSON (no markdown fences, no commentary) matching this \
exact schema:

{
  "summary": "3-6 sentence plain-English summary of the discussion",
  "key_topics": ["short topic phrase", ...],
  "actions": [
    {"description": "...", "owner": "name or null", "deadline": "YYYY-MM-DD or null",
     "priority": "low|medium|high", "source_quote": "short supporting quote"}
  ],
  "decisions": [
    {"description": "...", "decided_by": "name or null", "rationale": "short reason or null"}
  ],
  "risks": [
    {"description": "...", "severity": "low|medium|high", "mitigation": "short mitigation or null"}
  ],
  "questions": [
    {"question": "...", "raised_by": "name or null"}
  ]
}

Rules:
- Resolve relative dates (e.g. "next Friday", "by Wednesday") against the \
provided meeting date into an absolute YYYY-MM-DD date.
- If no owner is stated for an action item, set owner to null - never guess.
- Keep action item descriptions short, imperative, and specific.
- Only extract what is actually stated or clearly implied in the transcript.
- Output strictly valid JSON, nothing else."""


def _call_claude(transcript_text: str, meeting_date: datetime) -> Dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    user_msg = (
        f"Meeting date (for resolving relative dates): {meeting_date.date().isoformat()}\n\n"
        f"Transcript:\n{transcript_text}"
    )
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = "".join(block.text for block in resp.content if block.type == "text")
    raw = raw.strip()
    # strip accidental markdown fences
    raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


# --------------------------------------------------------------------------
# Offline fallback: simple heuristic extraction so the app works without an
# API key (useful for grading/demoing the pipeline end-to-end offline).
# --------------------------------------------------------------------------
_OWNER_RE = re.compile(
    r"\b([A-Z][a-z]+)\s+(?:will|to|agreed to|is going to)\b"
)
_DEADLINE_HINTS = {
    "next friday": 5, "next monday": 8, "next wednesday": 3,
    "by friday": 5, "by monday": 8, "by wednesday": 3, "next week": 7,
}


def _heuristic_extract(transcript_text: str, meeting_date: datetime) -> Dict[str, Any]:
    sentences = re.split(r"(?<=[.!?])\s+", transcript_text.strip())
    actions, decisions, risks, questions = [], [], [], []

    for sent in sentences:
        low = sent.lower()
        owner_match = _OWNER_RE.search(sent)
        owner = owner_match.group(1) if owner_match else None
        deadline = None
        for hint, days in _DEADLINE_HINTS.items():
            if hint in low:
                deadline = (meeting_date + timedelta(days=days)).date().isoformat()
                break

        if any(k in low for k in ["will ", " to follow up", "agreed to", "action item"]):
            actions.append({
                "description": sent.strip(),
                "owner": owner,
                "deadline": deadline,
                "priority": "medium",
                "source_quote": sent.strip()[:140],
            })
        elif any(k in low for k in ["decided", "decision was", "it was decided"]):
            decisions.append({"description": sent.strip(), "decided_by": owner, "rationale": None})
        elif any(k in low for k in ["risk", "blocked", "concern", "at risk"]):
            risks.append({"description": sent.strip(), "severity": "medium", "mitigation": None})
        elif "?" in sent or "open question" in low:
            questions.append({"question": sent.strip(), "raised_by": owner})

    summary = " ".join(sentences[:3]) if sentences else ""
    key_topics = list({s.split()[0] for s in sentences[:5] if s})[:5]

    return {
        "summary": summary,
        "key_topics": key_topics,
        "actions": actions,
        "decisions": decisions,
        "risks": risks,
        "questions": questions,
    }


def analyze_transcript(transcript_text: str, meeting_date: datetime | None = None) -> Dict[str, Any]:
    meeting_date = meeting_date or datetime.utcnow()
    if not transcript_text.strip():
        return {"summary": "", "key_topics": [], "actions": [], "decisions": [], "risks": [], "questions": []}

    if ANTHROPIC_API_KEY:
        try:
            return _call_claude(transcript_text, meeting_date)
        except Exception:
            # graceful degrade rather than a hard 500 for demo robustness
            return _heuristic_extract(transcript_text, meeting_date)
    return _heuristic_extract(transcript_text, meeting_date)


def parse_deadline(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
