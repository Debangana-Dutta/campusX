from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import User, current_user, require_roles
from app.services.audit import log as audit
from app.services.exams.scheduler import schedule_exams
from app.state import STATE

router = APIRouter(prefix="/exams")


@router.get("")
def list_exams(user: User = Depends(current_user)):
    if not STATE.imported:
        raise HTTPException(409, "dataset not imported yet")
    ds = STATE.ds
    visible = STATE.exams_published or user.role == "admin"          # drafts are visible to the admin office only
    allx = [e for e in (STATE.exams or []) if visible and (user.role != "student" or user.group_id in ds.exams[e["exam_id"]]["groups"])]
    return {"scheduled": STATE.exams is not None, "published": STATE.exams_published, "calendar": ds.raw["calendar"]["exam_week"],
            "note": None if visible else "No midsem examinations have been published yet. Please check again after the timetable is released.",
            "exams": [{**e, "title": ", ".join(ds.courses[c]["title"] for c in ds.exams[e["exam_id"]]["course_ids"]),
                       "course_ids": ds.exams[e["exam_id"]]["course_ids"], "duration_hours": ds.exams[e["exam_id"]]["duration_hours"],
                       "size": ds.exams[e["exam_id"]]["size"], "groups": ds.exams[e["exam_id"]]["groups"],
                       "seats_at_half_capacity": sum(ds.rooms[r]["capacity"] // 2 for r in e["rooms"])} for e in allx]}


@router.post("/publish")
def publish(body: dict | None = None, user: User = Depends(require_roles("admin"))):
    """Publish (or withdraw) the exam timetable. The exams must pass the official validator first."""
    unpublish = bool((body or {}).get("withdraw"))
    if not STATE.exams:
        raise HTTPException(409, "there is no exam timetable to publish")
    if not unpublish:
        v = STATE.validate()
        bad = [x for x in v.summary()["hard_violations"] if str(x["rule"]).startswith("E")]
        if bad:
            raise HTTPException(409, {"message": "exams failed official validation; not published", "errors": [x["detail"] for x in bad[:10]]})
    STATE.exams_published = not unpublish
    STATE.save()
    audit.record(user.id, "exams.withdraw" if unpublish else "exams.publish", "exams", {"count": len(STATE.exams)})
    from app.services.audit import notify
    if not unpublish:
        notify.notify("*", "The midsem examination timetable has been published.", "exam", "/app/exams", sender=user.id, dedupe=f"exams-published:{len(STATE.exams)}:{__import__('time').time_ns()}")
    return {"published": STATE.exams_published, "count": len(STATE.exams)}


@router.post("/generate")
def generate_exams(seed: int = 42, time_limit_s: int = 30, user: User = Depends(require_roles("admin"))):
    if not STATE.imported:
        raise HTTPException(409, "dataset not imported yet")
    r = schedule_exams(STATE.ds, seed=seed, time_limit_s=time_limit_s)
    if not r.has_solution:
        raise HTTPException(422, {"message": "no feasible exam schedule", "status": r.status, "diagnosis": r.diagnosis})
    STATE.exams = r.exams
    if STATE.assignment:
        STATE.validate()
    STATE.save()
    audit.record(user.id, "exams.generate", "exams", {"status": r.status, "penalty": r.penalty})
    STATE.exams_published = False           # a regenerated draft must be reviewed and published again
    STATE.save()
    return {"status": r.status, "penalty": r.penalty, "count": len(r.exams), "exams": r.exams}
