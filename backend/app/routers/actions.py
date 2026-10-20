from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/actions", tags=["actions"])


def _to_out(a: models.ActionItem) -> schemas.ActionItemOut:
    overdue = bool(a.deadline and a.deadline < date.today() and a.status != models.ActionStatus.DONE)
    out = schemas.ActionItemOut.model_validate(a)
    out.meeting_title = a.meeting.title if a.meeting else None
    out.is_overdue = overdue
    return out


@router.get("", response_model=List[schemas.ActionItemOut])
def list_actions(
    owner: Optional[str] = None,
    status: Optional[str] = None,
    project: Optional[str] = None,
    overdue_only: bool = False,
    db: Session = Depends(get_db),
):
    q = db.query(models.ActionItem).join(models.Meeting)
    if owner:
        q = q.filter(models.ActionItem.owner.ilike(f"%{owner}%"))
    if status:
        q = q.filter(models.ActionItem.status == status)
    if project:
        q = q.filter(models.Meeting.project == project)

    items = [_to_out(a) for a in q.order_by(models.ActionItem.deadline.asc().nullslast()).all()]
    if overdue_only:
        items = [i for i in items if i.is_overdue]
    return items


@router.get("/{action_id}", response_model=schemas.ActionItemOut)
def get_action(action_id: str, db: Session = Depends(get_db)):
    a = db.get(models.ActionItem, action_id)
    if not a:
        raise HTTPException(404, "Action item not found")
    return _to_out(a)


@router.put("/{action_id}", response_model=schemas.ActionItemOut)
def update_action(action_id: str, body: schemas.ActionItemUpdate, db: Session = Depends(get_db)):
    a = db.get(models.ActionItem, action_id)
    if not a:
        raise HTTPException(404, "Action item not found")

    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in [s.value for s in models.ActionStatus]:
        raise HTTPException(400, f"Invalid status. Options: {[s.value for s in models.ActionStatus]}")

    for field, value in data.items():
        setattr(a, field, value)

    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.delete("/{action_id}")
def delete_action(action_id: str, db: Session = Depends(get_db)):
    a = db.get(models.ActionItem, action_id)
    if not a:
        raise HTTPException(404, "Action item not found")
    db.delete(a)
    db.commit()
    return {"deleted": action_id}
