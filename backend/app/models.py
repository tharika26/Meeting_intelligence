import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Enum, Float, Integer, Date
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:12]


class MeetingStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class ActionStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String, nullable=False, default="Untitled Meeting")
    project = Column(String, nullable=True, index=True)
    audio_path = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    status = Column(Enum(MeetingStatus), default=MeetingStatus.UPLOADED, nullable=False)
    meeting_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # analysis outputs
    summary = Column(Text, nullable=True)
    key_topics = Column(Text, nullable=True)  # JSON-encoded list

    transcript = relationship("Transcript", back_populates="meeting", uselist=False,
                               cascade="all, delete-orphan")
    actions = relationship("ActionItem", back_populates="meeting", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="meeting", cascade="all, delete-orphan")
    risks = relationship("Risk", back_populates="meeting", cascade="all, delete-orphan")
    questions = relationship("OpenQuestion", back_populates="meeting", cascade="all, delete-orphan")


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(String, primary_key=True, default=gen_id)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False)
    full_text = Column(Text, nullable=False, default="")
    segments_json = Column(Text, nullable=True)  # JSON list of {start,end,speaker,text}
    language = Column(String, nullable=True, default="en")
    engine = Column(String, nullable=True)  # which STT backend produced this
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="transcript")


class ActionItem(Base):
    __tablename__ = "action_items"

    id = Column(String, primary_key=True, default=gen_id)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False)
    description = Column(Text, nullable=False)
    owner = Column(String, nullable=True, index=True)
    deadline = Column(Date, nullable=True)
    status = Column(Enum(ActionStatus), default=ActionStatus.OPEN, nullable=False)
    priority = Column(String, nullable=True, default="medium")  # low/medium/high
    source_quote = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="actions")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(String, primary_key=True, default=gen_id)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False)
    description = Column(Text, nullable=False)
    decided_by = Column(String, nullable=True)
    rationale = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="decisions")


class Risk(Base):
    __tablename__ = "risks"

    id = Column(String, primary_key=True, default=gen_id)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String, nullable=True, default="medium")  # low/medium/high
    mitigation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="risks")


class OpenQuestion(Base):
    __tablename__ = "open_questions"

    id = Column(String, primary_key=True, default=gen_id)
    meeting_id = Column(String, ForeignKey("meetings.id"), nullable=False)
    question = Column(Text, nullable=False)
    raised_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="questions")
