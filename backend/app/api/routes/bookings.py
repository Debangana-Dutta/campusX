"""Booking requests. The engine proposes; humans confirm; hard rules are re-checked at every confirmation."""
from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.auth import DATASET_ROLE, User, current_user, require_roles
from app.models.db import BookingRecord, Notification, session_scope
from app.schemas.api import BookingIn, DecisionIn
from app.services.audit import log as audit
from app.services.bookings.engine import BookingEngine
from app.state import STATE

router = APIRouter(prefix="/bookings")


def _engine() -> BookingEngine:
    if not STATE.imported or not STATE.assignment:
        raise HTTPException(409, "generate a timetable first (POST /api/timetable/generate)")
    return BookingEngine(STATE.ds, STATE.assignment)


def _confirmed() -> list[dict[str, Any]]:
    out = []
    ds = STATE.ds
    for d in (STATE.outcome.decisions if STATE.outcome else []):
        if d.status in ("approved", "alternative_offered") and d.room_id:
            out.append({**d.as_dict(), "_request": ds.requests[d.request_id]})
    with session_scope() as s:
        for b in s.scalars(select(BookingRecord).where(BookingRecord.state == "confirmed")):
            if b.decision.get("room_id"):
                out.append({**b.decision, "_request": b.request})
    return out


def _view(b: BookingRecord) -> dict[str, Any]:
    return {"id": b.id, "source": "user", "requester_id": b.requester_id, "state": b.state, "request": b.request,
            "decision": b.decision, "decided_by": b.decided_by, "created_at": b.created_at.isoformat()}


def _needs_human(req: dict, dec: dict, eng: BookingEngine) -> str | None:
    if dec["status"] == "alternative_offered":
        return "alternative placement needs approval"
    if dec["status"] == "approved":
        room = eng.ds.rooms[dec["room_id"]]
        if room["type"].startswith("lab_") or room["type"] == "workshop":
            return "lab booking needs the department coordinator or an admin"
    return None


@router.get("")
def list_bookings(user: User = Depends(current_user)):
    ds = STATE.ds if STATE.imported else None
    items: list[dict[str, Any]] = []
    if ds and STATE.outcome and user.role != "club_representative":
        for d in STATE.outcome.decisions:
            r = ds.requests[d.request_id]
            items.append({"id": d.request_id, "source": "dataset", "requester": r["requester"], "title": r["title"],
                          "request": r, "decision": d.as_dict(),
                          "state": "cancelled" if d.code == "cancelled" else d.status})
    with session_scope() as s:
        q = select(BookingRecord)
        if user.role in ("club_representative", "faculty"):
            q = q.where(BookingRecord.requester_id == user.id)
        items += [_view(b) for b in s.scalars(q)]
    return {"count": len(items), "bookings": items}


@router.post("", status_code=201)
def create_booking(body: BookingIn, user: User = Depends(current_user)):
    eng = _engine()
    longest = max(w.to_period - w.from_period + 1 for w in body.windows)
    if body.duration_periods > longest:
        raise HTTPException(422, {"needs_clarification": True,
                                  "message": f"The window is {longest} period(s) long but the event needs {body.duration_periods}. "
                                             "Widen the window or shorten the event."})
    if body.requested_category == "institute_event" and user.role not in ("admin",):
        pass  # not rejected: the engine caps the *effective* category by role, and the reason says so
    with session_scope() as s:
        n = len(list(s.scalars(select(BookingRecord.id)))) + 1
    bid = f"UR-{n:04d}"
    req = {"id": bid, "submitted_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds"),
           "requester": user.org or user.name, "role": DATASET_ROLE[user.role],
           "department": body.department or user.department, "requested_category": body.requested_category,
           "title": body.title, "attendance": body.attendance, "duration_periods": body.duration_periods,
           "windows": [w.model_dump() for w in body.windows], "room_types": body.room_types, "needs": body.needs,
           "requested_room": body.requested_room, "mandatory_for_groups": body.mandatory_for_groups, "series_id": None,
           "raw_text": body.raw_text}
    ds = eng.ds
    bad_groups = [g for g in req["mandatory_for_groups"] if g not in ds.groups]
    if bad_groups:
        raise HTTPException(422, f"unknown student group(s): {bad_groups}")
    st = eng.state_with(_confirmed(), STATE.outcome.session_overrides if STATE.outcome else [])
    dec = eng.decide_one(st, req)
    human = _needs_human(req, dec.as_dict(), eng) if dec.status != "rejected" else None
    state = "rejected" if dec.status == "rejected" else ("proposed" if human else "confirmed")
    rec = BookingRecord(id=bid, requester_id=user.id, request=req, decision={**dec.as_dict(), "needs_approval": human},
                        state=state)
    with session_scope() as s:
        s.add(rec)
    audit.record(user.id, "booking.create", bid, {"status": dec.status, "state": state})
    return _view(rec)


@router.get("/{booking_id}")
def booking_detail(booking_id: str, user: User = Depends(current_user)):
    if booking_id.startswith("UR-"):
        with session_scope() as s:
            b = s.get(BookingRecord, booking_id)
            if not b:
                raise HTTPException(404, "booking not found")
            if user.role in ("club_representative", "faculty") and b.requester_id != user.id:
                raise HTTPException(403, "not your booking")
            return {**_view(b), "audit": audit.recent(50, booking_id)}
    if STATE.outcome:
        for d in STATE.outcome.decisions:
            if d.request_id == booking_id:
                if user.role == "club_representative":
                    raise HTTPException(403, "not your booking")
                return {"id": booking_id, "source": "dataset", "request": STATE.ds.requests[booking_id],
                        "decision": d.as_dict(), "audit": audit.recent(50, booking_id)}
    raise HTTPException(404, "booking not found")


@router.post("/{booking_id}/decision")
def decide(booking_id: str, body: DecisionIn, user: User = Depends(require_roles("admin", "department_coordinator"))):
    with session_scope() as s:
        b = s.get(BookingRecord, booking_id)
        if not b:
            raise HTTPException(404, "only user-submitted bookings can be decided here")
        if b.requester_id == user.id:
            raise HTTPException(403, "you cannot approve or reject your own request")
        if b.state not in ("proposed",):
            raise HTTPException(409, f"booking is already {b.state}")
        req, dec = b.request, dict(b.decision)
        if body.action == "reject":
            if not body.reason.strip():
                raise HTTPException(422, "a reason is required to reject")
            b.state, b.decided_by = "rejected", user.id
            dec.update(status="rejected", reason=body.reason)
            b.decision = dec
            s.add(Notification(user_id=b.requester_id, message=f"{booking_id} was rejected: {body.reason}"))
            audit.record(user.id, "booking.reject", booking_id, {"reason": body.reason})
            return _view(b)
        room = body.room_id or dec.get("room_id")
        day = body.day or dec.get("day")
        start = body.start_period or dec.get("start_period")
        if not (room and day and start):
            raise HTTPException(422, "nothing to approve: the engine proposed no placement")
        end = start + req["duration_periods"] - 1
        # coordinator scope: only their department's labs
        if user.role == "department_coordinator":
            rtype = STATE.ds.rooms[room]["type"] if room in STATE.ds.rooms else ""
            if not (rtype.startswith("lab_") or rtype == "workshop") or req.get("department") != user.department:
                raise HTTPException(403, "department coordinators may only approve bookings of their department's labs")
        eng = _engine()
        st = eng.state_with(_confirmed(), STATE.outcome.session_overrides if STATE.outcome else [])
        errs = eng.validate_placement(st, req, room, day, start, end)
        if errs:
            raise HTTPException(409, {"message": "approval refused: placement breaks hard constraints", "errors": errs})
        dec.update(status="approved" if dec["status"] == "approved" else dec["status"], room_id=room, day=day,
                   start_period=start, end_period=end, needs_approval=None)
        b.decision, b.state, b.decided_by = dec, "confirmed", user.id
        s.add(Notification(user_id=b.requester_id, message=f"{booking_id} confirmed: {room} {day} P{start}-P{end}"))
        audit.record(user.id, "booking.approve", booking_id, {"room": room, "day": day, "start": start})
        return _view(b)


@router.post("/{booking_id}/cancel")
def cancel(booking_id: str, user: User = Depends(current_user)):
    with session_scope() as s:
        b = s.get(BookingRecord, booking_id)
        if not b:
            raise HTTPException(404, "only user-submitted bookings can be cancelled here")
        if b.requester_id != user.id and user.role != "admin":
            raise HTTPException(403, "only the requester or an admin can cancel")
        if b.state == "cancelled":
            raise HTTPException(409, "already cancelled")
        b.state = "cancelled"
        audit.record(user.id, "booking.cancel", booking_id, {})
        return _view(b)
