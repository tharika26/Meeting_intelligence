import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import UPLOAD_DIR, ALLOWED_AUDIO_EXT, MAX_UPLOAD_MB
from app.database import get_db
from app.services import transcription, llm_analysis
from app.services.search import search_meetings

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.post("/upload", response_model=schemas.MeetingUploadOut)
async def upload_meeting(
    file: UploadFile = File(...),
    title: str = Form("Untitled Meeting"),
    project: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_AUDIO_EXT:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_AUDIO_EXT)}")

    meeting = models.Meeting(title=title, project=project, original_filename=file.filename,
                              status=models.MeetingStatus.UPLOADED, meeting_date=datetime.utcnow())
    db.add(meeting)
    db.flush()  # get generated id

    dest = UPLOAD_DIR / f"{meeting.id}{ext}"
    size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                db.rollback()
                raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB}MB limit")
            out.write(chunk)

    meeting.audio_path = str(dest)
    db.commit()
    db.refresh(meeting)

    return schemas.MeetingUploadOut(
        id=meeting.id, title=meeting.title, status=meeting.status.value,
        message="Uploaded. Call POST /meetings/transcribe next.",
    )


@router.post("/transcribe", response_model=schemas.TranscriptOut)
def transcribe_meeting(meeting_id: str, body: schemas.TranscribeRequest = schemas.TranscribeRequest(),
                        db: Session = Depends(get_db)):
    meeting = db.get(models.Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    meeting.status = models.MeetingStatus.TRANSCRIBING
    db.commit()

    try:
        if body.manual_text:
            result = transcription.TranscriptionResult(
                full_text=body.manual_text,
                segments=[{"start": 0, "end": 0, "speaker": None, "text": body.manual_text}],
                language="en", engine="manual",
            )
        else:
            if not meeting.audio_path:
                raise HTTPException(400, "No audio uploaded for this meeting")
            result = transcription.transcribe_audio(Path(meeting.audio_path))

        existing = db.query(models.Transcript).filter_by(meeting_id=meeting.id).first()
        if existing:
            db.delete(existing)
            db.flush()

        t = models.Transcript(
            meeting_id=meeting.id,
            full_text=result.full_text,
            segments_json=transcription.segments_to_json(result.segments),
            language=result.language,
            engine=result.engine,
        )
        db.add(t)
        meeting.status = models.MeetingStatus.TRANSCRIBED
        db.commit()
        db.refresh(t)
    except HTTPException:
        raise
    except Exception as e:
        meeting.status = models.MeetingStatus.FAILED
        db.commit()
        raise HTTPException(500, f"Transcription failed: {e}")

    return schemas.TranscriptOut(
        meeting_id=meeting.id, full_text=t.full_text,
        segments=json.loads(t.segments_json or "[]"), language=t.language, engine=t.engine,
    )


@router.post("/analyze", response_model=schemas.MeetingAnalysisOut)
def analyze_meeting(meeting_id: str, body: schemas.AnalyzeRequest = schemas.AnalyzeRequest(),
                     db: Session = Depends(get_db)):
    meeting = db.get(models.Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    if not meeting.transcript:
        raise HTTPException(400, "Meeting has no transcript yet. Call POST /meetings/transcribe first.")
    if meeting.status == models.MeetingStatus.ANALYZED and not body.force:
        raise HTTPException(409, "Already analyzed. Pass force=true to re-run.")

    meeting.status = models.MeetingStatus.ANALYZING
    db.commit()

    try:
        result = llm_analysis.analyze_transcript(meeting.transcript.full_text, meeting.meeting_date)

        # clear previous analysis (idempotent re-analyze)
        for coll in (meeting.actions, meeting.decisions, meeting.risks, meeting.questions):
            for item in list(coll):
                db.delete(item)
        db.flush()

        meeting.summary = result.get("summary", "")
        meeting.key_topics = json.dumps(result.get("key_topics", []))

        for a in result.get("actions", []):
            db.add(models.ActionItem(
                meeting_id=meeting.id, description=a.get("description", ""),
                owner=a.get("owner"), deadline=llm_analysis.parse_deadline(a.get("deadline")),
                priority=a.get("priority", "medium"), source_quote=a.get("source_quote"),
            ))
        for d in result.get("decisions", []):
            db.add(models.Decision(
                meeting_id=meeting.id, description=d.get("description", ""),
                decided_by=d.get("decided_by"), rationale=d.get("rationale"),
            ))
        for r in result.get("risks", []):
            db.add(models.Risk(
                meeting_id=meeting.id, description=r.get("description", ""),
                severity=r.get("severity", "medium"), mitigation=r.get("mitigation"),
            ))
        for q in result.get("questions", []):
            db.add(models.OpenQuestion(
                meeting_id=meeting.id, question=q.get("question", ""), raised_by=q.get("raised_by"),
            ))

        meeting.status = models.MeetingStatus.ANALYZED
        db.commit()
        db.refresh(meeting)
    except Exception as e:
        meeting.status = models.MeetingStatus.FAILED
        db.commit()
        raise HTTPException(500, f"Analysis failed: {e}")

    return schemas.MeetingAnalysisOut(
        meeting_id=meeting.id,
        summary=meeting.summary or "",
        key_topics=json.loads(meeting.key_topics or "[]"),
        actions=[schemas.ActionItemOut.model_validate(a) for a in meeting.actions],
        decisions=[schemas.DecisionOut.model_validate(d) for d in meeting.decisions],
        risks=[schemas.RiskOut.model_validate(r) for r in meeting.risks],
        questions=[schemas.OpenQuestionOut.model_validate(q) for q in meeting.questions],
    )


@router.get("", response_model=List[schemas.MeetingOut])
def list_meetings(project: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Meeting)
    if project:
        q = q.filter(models.Meeting.project == project)
    return q.order_by(models.Meeting.created_at.desc()).all()


@router.get("/{meeting_id}", response_model=schemas.MeetingAnalysisOut)
def get_meeting(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.get(models.Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    return schemas.MeetingAnalysisOut(
        meeting_id=meeting.id,
        summary=meeting.summary or "",
        key_topics=json.loads(meeting.key_topics or "[]"),
        actions=[schemas.ActionItemOut.model_validate(a) for a in meeting.actions],
        decisions=[schemas.DecisionOut.model_validate(d) for d in meeting.decisions],
        risks=[schemas.RiskOut.model_validate(r) for r in meeting.risks],
        questions=[schemas.OpenQuestionOut.model_validate(q) for q in meeting.questions],
    )


@router.get("/{meeting_id}/transcript", response_model=schemas.TranscriptOut)
def get_transcript(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.get(models.Meeting, meeting_id)
    if not meeting or not meeting.transcript:
        raise HTTPException(404, "Transcript not found")
    t = meeting.transcript
    return schemas.TranscriptOut(
        meeting_id=meeting.id, full_text=t.full_text,
        segments=json.loads(t.segments_json or "[]"), language=t.language, engine=t.engine,
    )


@router.post("/search", response_model=schemas.SearchResponse)
def search(body: schemas.SearchRequest, db: Session = Depends(get_db)):
    q = db.query(models.Meeting)
    if body.project:
        q = q.filter(models.Meeting.project == body.project)
    meetings = q.all()
    hits = search_meetings(body.query, meetings, top_k=body.top_k)
    return schemas.SearchResponse(
        query=body.query,
        results=[
            schemas.SearchHit(
                meeting_id=m.id, title=m.title, project=m.project,
                score=round(score, 4), snippet=snippet, meeting_date=m.meeting_date,
            )
            for m, score, snippet in hits
        ],
    )
