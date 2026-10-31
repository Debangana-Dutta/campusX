from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import User, require_roles

current_user = require_roles("admin", "faculty", "department_coordinator", "club_representative")
from app.state import STATE

router = APIRouter(prefix="/reports")
TEACHING_SLOTS_PER_ROOM = 45


@router.get("/room-utilisation")
def room_utilisation(user: User = Depends(current_user)):
    if not STATE.assignment:
        raise HTTPException(409, "no timetable yet")
    ds = STATE.ds
    teach: dict[str, int] = {r: 0 for r in ds.rooms}
    for sid, (d, p, r) in STATE.assignment.items():
        teach[r] += ds.sessions[sid]["duration"]
    event: dict[str, int] = {r: 0 for r in ds.rooms}
    for dec in (STATE.outcome.decisions if STATE.outcome else []):
        if dec.status in ("approved", "alternative_offered") and dec.room_id:
            event[dec.room_id] += dec.end_period - dec.start_period + 1
    rows = []
    for rid, room in ds.rooms.items():
        closed = len(ds.room_unavail.get(rid, ()))
        avail = TEACHING_SLOTS_PER_ROOM - len([1 for (_, q) in ds.room_unavail.get(rid, ()) if q <= 9])
        rows.append({"room_id": rid, "type": room["type"], "teaching_hours": teach[rid],
                     "available_teaching_hours": avail,
                     "utilisation_pct": round(100 * teach[rid] / avail, 1) if avail else 0.0,
                     "spectra_event_hours": event[rid]})
    return {"rooms": sorted(rows, key=lambda r: -r["utilisation_pct"])}


@router.get("/validation")
def validation_report(user: User = Depends(current_user)):
    if not STATE.assignment:
        raise HTTPException(409, "no timetable yet")
    return STATE.validate().summary()
