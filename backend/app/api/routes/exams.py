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
    allx = [e for e in (STATE.exams or []) if user.role != "student" or user.group_id in ds.exams[e["exam_id"]]["groups"]]
    return {"scheduled": STATE.exams is not None, "calendar": ds.raw["calendar"]["exam_week"],
            "exams": [{**e, "title": ", ".join(ds.courses[c]["title"] for c in ds.exams[e["exam_id"]]["course_ids"]), "size": ds.exams[e["exam_id"]]["size"], "groups": ds.exams[e["exam_id"]]["groups"],
                       "seats_at_half_capacity": sum(ds.rooms[r]["capacity"] // 2 for r in e["rooms"])}
                      for e in allx]}


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
    from app.services.audit import notify
    notify.notify("*", "The exam timetable was regenerated.", "exam", "/app/exams")
    return {"status": r.status, "penalty": r.penalty, "count": len(r.exams), "exams": r.exams}
