from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


# ---------- Meeting ----------
class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    project: Optional[str] = None
    status: str
    original_filename: Optional[str] = None
    duration_seconds: Optional[float] = None
    meeting_date: Optional[datetime] = None
    created_at: datetime
    summary: Optional[str] = None


class MeetingUploadOut(BaseModel):
    id: str
    title: str
    status: str
    message: str


# ---------- Transcript ----------
class TranscriptSegment(BaseModel):
    start: float
    end: float
    speaker: Optional[str] = None
    text: str


class TranscriptOut(BaseModel):
    meeting_id: str
    full_text: str
    segments: List[TranscriptSegment] = []
    language: Optional[str] = "en"
    engine: Optional[str] = None


class TranscribeRequest(BaseModel):
    # Optional manual transcript override (useful for demos / already-transcribed text)
    manual_text: Optional[str] = None


# ---------- Analysis ----------
class AnalyzeRequest(BaseModel):
    force: bool = False


class ActionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meeting_id: str
    description: str
    owner: Optional[str] = None
    deadline: Optional[date] = None
    status: str
    priority: Optional[str] = None
    source_quote: Optional[str] = None
    created_at: datetime
    meeting_title: Optional[str] = None
    is_overdue: Optional[bool] = False


class ActionItemUpdate(BaseModel):
    description: Optional[str] = None
    owner: Optional[str] = None
    deadline: Optional[date] = None
    status: Optional[str] = None
    priority: Optional[str] = None


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meeting_id: str
    description: str
    decided_by: Optional[str] = None
    rationale: Optional[str] = None
    created_at: datetime
    meeting_title: Optional[str] = None


class RiskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meeting_id: str
    description: str
    severity: Optional[str] = None
    mitigation: Optional[str] = None
    meeting_title: Optional[str] = None


class OpenQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meeting_id: str
    question: str
    raised_by: Optional[str] = None
    meeting_title: Optional[str] = None


class MeetingAnalysisOut(BaseModel):
    meeting_id: str
    summary: str
    key_topics: List[str]
    actions: List[ActionItemOut]
    decisions: List[DecisionOut]
    risks: List[RiskOut]
    questions: List[OpenQuestionOut]


# ---------- Search ----------
class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    project: Optional[str] = None


class SearchHit(BaseModel):
    meeting_id: str
    title: str
    project: Optional[str] = None
    score: float
    snippet: str
    meeting_date: Optional[datetime] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchHit]


# ---------- Dashboard ----------
class DashboardStats(BaseModel):
    total_meetings: int
    total_actions: int
    open_actions: int
    overdue_actions: int
    done_actions: int
    total_decisions: int
    total_risks: int
    actions_by_owner: dict
    overdue_by_owner: dict
