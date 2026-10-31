from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.core.auth import User, current_user, require_roles
from app.schemas.api import GenerateIn
from app.services.audit import log as audit
from app.services.scheduling.solver import to_schedule_sessions
from app.state import STATE

router = APIRouter(prefix="/timetable")


def _ready():
    if not STATE.imported:
        raise HTTPException(409, "dataset not imported yet")
    if not STATE.assignment:
        raise HTTPException(409, "no timetable yet: POST /api/timetable/generate")


def _entry(sid: str, slot) -> dict[str, Any]:
    ds = STATE.ds
    s = ds.sessions[sid]
    d, p, r = slot
    return {"session_id": sid, "course_id": s["course_id"], "kind": s["kind"], "day": d, "start_period": p,
            "end_period": p + s["duration"] - 1, "room_id": r, "faculty_id": s["faculty_id"], "groups": s["groups"],
            "basket_slot": s.get("basket_slot")}


@router.post("/generate")
def generate(body: GenerateIn, user: User = Depends(require_roles("admin"))):
    st = get_settings()
    out = STATE.generate(seed=body.seed if body.seed is not None else st.solver_seed, time_limit_s=body.time_limit_s,
                         include_exams=body.include_exams, include_bookings=body.include_bookings,
                         hint_from_saved=not body.fresh)
    audit.record(user.id, "timetable.generate", "timetable", {k: out.get(k) for k in ("ok", "status", "accepted")})
    if not out["ok"]:
        raise HTTPException(422, {"message": "no feasible timetable was produced", **{k: out.get(k) for k in ("status", "diagnosis")}})
    return out


@router.get("")
def get_timetable(user: User = Depends(current_user)):
    _ready()
    return {"sessions": [_entry(s, v) for s, v in sorted(STATE.assignment.items())],
            "solver": STATE.solver_info, "validation": STATE.last_validation,
            "week7_overrides": STATE.outcome.session_overrides if STATE.outcome else []}


@router.get("/group/{group_id}")
def by_group(group_id: str, user: User = Depends(current_user)):
    _ready()
    if group_id not in STATE.ds.groups:
        raise HTTPException(404, f"unknown group {group_id}")
    return {"group_id": group_id, "sessions": [_entry(s, v) for s, v in sorted(STATE.assignment.items())
                                               if group_id in STATE.ds.sessions[s]["groups"]]}


@router.get("/faculty/{faculty_id}")
def by_faculty(faculty_id: str, user: User = Depends(current_user)):
    _ready()
    if faculty_id not in STATE.ds.faculty:
        raise HTTPException(404, f"unknown faculty {faculty_id}")
    if user.role == "faculty" and user.faculty_id != faculty_id:
        raise HTTPException(403, "faculty may only view their own timetable")
    return {"faculty_id": faculty_id, "sessions": [_entry(s, v) for s, v in sorted(STATE.assignment.items())
                                                   if STATE.ds.sessions[s]["faculty_id"] == faculty_id]}


@router.get("/room/{room_id}")
def by_room(room_id: str, user: User = Depends(current_user)):
    _ready()
    if room_id not in STATE.ds.rooms:
        raise HTTPException(404, f"unknown room {room_id}")
    ev = [d.as_dict() for d in (STATE.outcome.decisions if STATE.outcome else [])
          if d.room_id == room_id and d.status in ("approved", "alternative_offered")]
    return {"room_id": room_id, "sessions": [_entry(s, v) for s, v in sorted(STATE.assignment.items()) if v[2] == room_id],
            "spectra_bookings": ev}


@router.post("/validate")
def validate(user: User = Depends(current_user)):
    _ready()
    v = STATE.validate()
    audit.record(user.id, "timetable.validate", "timetable", {"accepted": v.accepted})
    return v.summary()


@router.get("/export")
def export(user: User = Depends(require_roles("admin"))):
    """Export schedule.json. Refused unless the OFFICIAL validator accepts the current state."""
    _ready()
    sched = STATE.schedule()
    v = STATE.validate(sched)
    if not v.accepted:
        raise HTTPException(409, {"message": "export refused: the official validator does not accept the current schedule",
                                  "validation": v.summary()})
    audit.record(user.id, "timetable.export", "schedule.json", {"soft": v.summary()["soft_total"]})
    return sched
