from collections import defaultdict
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(tags=["insights"])


@router.get("/decisions", response_model=List[schemas.DecisionOut])
def list_decisions(project: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Decision).join(models.Meeting)
    if project:
        q = q.filter(models.Meeting.project == project)
    out = []
    for d in q.order_by(models.Decision.created_at.desc()).all():
        item = schemas.DecisionOut.model_validate(d)
        item.meeting_title = d.meeting.title if d.meeting else None
        out.append(item)
    return out


@router.get("/risks", response_model=List[schemas.RiskOut])
def list_risks(project: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Risk).join(models.Meeting)
    if project:
        q = q.filter(models.Meeting.project == project)
    out = []
    for r in q.order_by(models.Risk.created_at.desc()).all():
        item = schemas.RiskOut.model_validate(r)
        item.meeting_title = r.meeting.title if r.meeting else None
        out.append(item)
    return out


@router.get("/questions", response_model=List[schemas.OpenQuestionOut])
def list_questions(project: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.OpenQuestion).join(models.Meeting)
    if project:
        q = q.filter(models.Meeting.project == project)
    out = []
    for item_ in q.order_by(models.OpenQuestion.created_at.desc()).all():
        item = schemas.OpenQuestionOut.model_validate(item_)
        item.meeting_title = item_.meeting.title if item_.meeting else None
        out.append(item)
    return out


@router.get("/dashboard/stats", response_model=schemas.DashboardStats)
def dashboard_stats(project: Optional[str] = None, db: Session = Depends(get_db)):
    mq = db.query(models.Meeting)
    if project:
        mq = mq.filter(models.Meeting.project == project)
    meetings = mq.all()
    meeting_ids = {m.id for m in meetings}

    aq = db.query(models.ActionItem)
    actions = [a for a in aq.all() if a.meeting_id in meeting_ids]

    today = date.today()
    open_actions = [a for a in actions if a.status != models.ActionStatus.DONE]
    overdue_actions = [a for a in open_actions if a.deadline and a.deadline < today]
    done_actions = [a for a in actions if a.status == models.ActionStatus.DONE]

    by_owner = defaultdict(int)
    overdue_by_owner = defaultdict(int)
    for a in actions:
        owner = a.owner or "Unassigned"
        by_owner[owner] += 1
    for a in overdue_actions:
        owner = a.owner or "Unassigned"
        overdue_by_owner[owner] += 1

    dq = db.query(models.Decision)
    decisions = [d for d in dq.all() if d.meeting_id in meeting_ids]
    rq = db.query(models.Risk)
    risks = [r for r in rq.all() if r.meeting_id in meeting_ids]

    return schemas.DashboardStats(
        total_meetings=len(meetings),
        total_actions=len(actions),
        open_actions=len(open_actions),
        overdue_actions=len(overdue_actions),
        done_actions=len(done_actions),
        total_decisions=len(decisions),
        total_risks=len(risks),
        actions_by_owner=dict(by_owner),
        overdue_by_owner=dict(overdue_by_owner),
    )
