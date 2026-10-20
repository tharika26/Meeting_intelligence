"""
Populate the database with a few realistic demo meetings so the frontend
(Dashboard, Action Tracker, Decision Log, Search) has something to show
immediately, without needing a real audio file or LLM API key.

Run with:  python seed_data.py
"""
import json
from datetime import datetime, timedelta

from app.database import Base, engine, SessionLocal
from app import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# wipe existing demo data for idempotent re-seeding
db.query(models.ActionItem).delete()
db.query(models.Decision).delete()
db.query(models.Risk).delete()
db.query(models.OpenQuestion).delete()
db.query(models.Transcript).delete()
db.query(models.Meeting).delete()
db.commit()

MEETINGS = [
    {
        "title": "Sprint 14 Planning",
        "project": "Aurora Payments",
        "days_ago": 10,
        "summary": "Team reviewed sprint 13 velocity and planned sprint 14. Payments "
                    "vendor integration is blocked on sandbox credentials, pushing risk "
                    "onto the March 15 release date.",
        "transcript": "Priya opened the meeting and reviewed last sprint's velocity. "
                      "Ramesh raised a concern that the payments integration is blocked "
                      "on the vendor sandbox credentials, which is a risk to the March 15 "
                      "release. The team decided to move the beta launch date to March 22 "
                      "to absorb that risk. Ananya will follow up with the vendor and get "
                      "sandbox access by next Friday.",
        "actions": [
            {"description": "Follow up with payments vendor for sandbox access", "owner": "Ananya",
             "days_offset": 5, "priority": "high", "status": models.ActionStatus.OPEN},
            {"description": "Finish reporting dashboard UI", "owner": "Kiran",
             "days_offset": 3, "priority": "medium", "status": models.ActionStatus.IN_PROGRESS},
        ],
        "decisions": [
            {"description": "Move beta launch date from March 15 to March 22", "decided_by": "Priya",
             "rationale": "Absorb vendor sandbox delay risk"},
        ],
        "risks": [
            {"description": "Payments vendor sandbox access delay could block QA", "severity": "high",
             "mitigation": "Escalate to vendor account manager"},
        ],
        "questions": [
            {"question": "Does the mobile app need offline support in this release?", "raised_by": "Suresh"},
        ],
    },
    {
        "title": "Design Review - Checkout Flow",
        "project": "Aurora Payments",
        "days_ago": 25,
        "summary": "Reviewed the new checkout flow mockups. Agreed to require design "
                    "review sign-off before any API changes are merged going forward.",
        "transcript": "The team reviewed the new checkout flow mockups from the design "
                      "team. It was decided that all API changes going forward require a "
                      "design review before merging. Kiran will update the CI pipeline to "
                      "enforce this by next Wednesday. Ramesh flagged a risk that the "
                      "current rate limiter may not handle Black Friday traffic.",
        "actions": [
            {"description": "Update CI pipeline to enforce design review gate", "owner": "Kiran",
             "days_offset": -18, "priority": "medium", "status": models.ActionStatus.DONE},
        ],
        "decisions": [
            {"description": "All API changes require design review before merge", "decided_by": "Team",
             "rationale": "Reduce production incidents from unreviewed API changes"},
        ],
        "risks": [
            {"description": "Rate limiter may not handle Black Friday peak traffic", "severity": "medium",
             "mitigation": "Load test before November"},
        ],
        "questions": [],
    },
    {
        "title": "Stakeholder Sync - Rollout Plan",
        "project": "Aurora Payments",
        "days_ago": 2,
        "summary": "Discussed rollout plan draft and stakeholder review timing.",
        "transcript": "Suresh will draft the updated rollout plan and share it before "
                      "Monday's stakeholder review. Ananya reported the vendor sandbox "
                      "credentials finally arrived. The team agreed the March 22 beta date "
                      "still stands.",
        "actions": [
            {"description": "Draft updated rollout plan for stakeholder review", "owner": "Suresh",
             "days_offset": -1, "priority": "high", "status": models.ActionStatus.OPEN},
        ],
        "decisions": [],
        "risks": [],
        "questions": [],
    },
]

for m in MEETINGS:
    meeting_date = datetime.utcnow() - timedelta(days=m["days_ago"])
    meeting = models.Meeting(
        title=m["title"], project=m["project"], status=models.MeetingStatus.ANALYZED,
        meeting_date=meeting_date, summary=m["summary"], key_topics=json.dumps([]),
    )
    db.add(meeting)
    db.flush()

    db.add(models.Transcript(meeting_id=meeting.id, full_text=m["transcript"],
                              segments_json=json.dumps([]), language="en", engine="seed"))

    for a in m["actions"]:
        db.add(models.ActionItem(
            meeting_id=meeting.id, description=a["description"], owner=a["owner"],
            deadline=(meeting_date + timedelta(days=a["days_offset"])).date(),
            priority=a["priority"], status=a["status"],
        ))
    for d in m["decisions"]:
        db.add(models.Decision(meeting_id=meeting.id, **d))
    for r in m["risks"]:
        db.add(models.Risk(meeting_id=meeting.id, **r))
    for q in m["questions"]:
        db.add(models.OpenQuestion(meeting_id=meeting.id, **q))

db.commit()
print(f"Seeded {len(MEETINGS)} demo meetings.")
