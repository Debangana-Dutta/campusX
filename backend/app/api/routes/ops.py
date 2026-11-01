"""Priority order, manual scheduling, decision explanations, faculty assistant, and Admin data management."""
from __future__ import annotations

import copy
import datetime as dt
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.auth import DATASET_ROLE, User, current_user, require_roles
from app.models.db import BookingRecord, session_scope
from app.schemas.api import ManualBookingIn
from app.services.ai import explain, schedule_assistant
from app.services.audit import log as audit, notify
from app.services.bookings.engine import BookingEngine
from app.services.dataset.loader import Dataset, check_integrity
from app.state import STATE

router = APIRouter()
admin = require_roles("admin")
staff = require_roles("admin", "faculty", "department_coordinator", "club_representative")
FIXED_TOP = ["exam", "regular_session"]


# ---------------------------------------------------------------- priority order
@router.get("/admin/priority-order")
def get_priority(user: User = Depends(admin)):
    return {"order": STATE.live_raw["priority_order"], "default": STATE.raw["priority_order"], "fixed_top": FIXED_TOP,
            "note": "Exams and regular classes always outrank events (class displacement rules depend on it); the four event categories can be reordered."}


@router.put("/admin/priority-order")
def set_priority(body: dict, user: User = Depends(admin)):
    order = body.get("order")
    cur = STATE.live_raw["priority_order"]
    if not isinstance(order, list) or sorted(order) != sorted(cur):
        raise HTTPException(422, f"order must contain exactly these categories: {cur}")
    if order[:2] != FIXED_TOP:
        raise HTTPException(422, "exam and regular_session must stay first and second")
    STATE.live_raw["priority_order"] = order
    STATE.data_modified = True
    if STATE.assignment:
        STATE.outcome = BookingEngine(STATE.ds, STATE.assignment).decide()
        STATE.validate()
    STATE.save()
    audit.record(user.id, "priority.change", "priority_order", {"order": order})
    notify.notify("role:admin", f"Booking priority order changed to: {', '.join(order[2:])}.", "booking", "/app/bookings",
                  sender=user.id, dedupe=f"priority:{'|'.join(order)}:{dt.datetime.now().isoformat(timespec='minutes')}")
    return {"order": order, "bookings_redecided": bool(STATE.outcome)}


# ---------------------------------------------------------------- manual scheduling (same validation as automatic)
@router.post("/bookings/manual", status_code=201)
def manual_booking(body: ManualBookingIn, user: User = Depends(require_roles("admin", "department_coordinator", "faculty"))):
    if not STATE.assignment:
        raise HTTPException(409, "generate a timetable first")
    ds = STATE.ds
    if body.room_id not in ds.rooms:
        raise HTTPException(422, f"unknown room {body.room_id}")
    end = body.start_period + body.duration_periods - 1
    req = {"id": f"UR-{uuid.uuid4().hex[:8].upper()}", "submitted_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds"),
           "requester": user.name, "role": DATASET_ROLE[user.role], "department": body.department or user.department,
           "requested_category": body.requested_category, "title": body.title, "attendance": body.attendance,
           "duration_periods": body.duration_periods, "windows": [{"day": body.day, "from_period": body.start_period, "to_period": end}],
           "room_types": [ds.rooms[body.room_id]["type"]], "needs": body.needs, "requested_room": body.room_id,
           "mandatory_for_groups": body.mandatory_for_groups, "series_id": None, "raw_text": "manual scheduling"}
    bad = [g for g in req["mandatory_for_groups"] if g not in ds.groups]
    if bad:
        raise HTTPException(422, f"unknown student group(s): {bad}")
    from app.api.routes.bookings import _confirmed
    eng = BookingEngine(ds, STATE.assignment)
    st = eng.state_with(_confirmed(), STATE.outcome.session_overrides if STATE.outcome else [])
    errs = eng.validate_placement(st, req, body.room_id, body.day, body.start_period, end)   # the SAME checks as automatic decisions
    if errs:
        raise HTTPException(409, {"message": "this placement breaks hard constraints", "errors": errs,
                                  "note": "Confirmed bookings and classes are never overwritten by a manual booking."})
    eff = ds.effective_category(req)
    if user.role == "department_coordinator" and req["department"] != user.department:
        raise HTTPException(403, "department coordinators schedule events for their own department")
    state = "confirmed" if user.role in ("admin", "department_coordinator") else "proposed"
    dec = {"request_id": req["id"], "status": "approved", "reason": f"Manually scheduled by {user.name} as {eff.replace('_', ' ')}: "
           f"{body.room_id} {body.day} P{body.start_period}-P{end}. All hard checks passed.", "effective_category": eff, "code": "manual",
           "room_id": body.room_id, "day": body.day, "start_period": body.start_period, "end_period": end,
           "needs_approval": None if state == "confirmed" else "faculty room request needs an admin or coordinator"}
    with session_scope() as s:
        s.add(BookingRecord(id=req["id"], requester_id=user.id, request=req, decision=dec, state=state))
        if state == "proposed":
            notify.notify("role:admin", f"{req['id']}: {user.name} requested {body.room_id} for '{body.title}'.", "booking", "/app/bookings",
                          sender=user.id, related_id=req["id"], dedupe=f"manual:{req['id']}", session=s)
    audit.record(user.id, "booking.manual", req["id"], {"room": body.room_id, "state": state})
    return {"id": req["id"], "state": state, "decision": dec}


# ---------------------------------------------------------------- explanations + faculty assistant
@router.get("/timetable/explain/{session_id}")
def explain_one(session_id: str, user: User = Depends(current_user)):
    if not STATE.assignment or session_id not in STATE.assignment:
        raise HTTPException(404, "session not found in the current timetable")
    s = STATE.ds.sessions[session_id]
    if user.role == "student" and user.group_id not in s["groups"]:
        raise HTTPException(403, "students may only see their own group's sessions")
    if user.role == "faculty" and s["faculty_id"] != user.faculty_id:
        raise HTTPException(403, "faculty may only see their own sessions")
    return explain.explain_session(STATE.ds, STATE.assignment, session_id, STATE.solver_info)


# ---------------------------------------------------------------- Admin data management (persisted, integrity-checked)
ENTITY = {"rooms": "rooms", "faculty": "faculty", "groups": "student_groups", "courses": "courses", "sessions": "sessions"}


def _commit(candidate: dict, user: User, what: str) -> None:
    rep = check_integrity(candidate)
    if not rep.ok:
        raise HTTPException(422, {"message": "change refused: it would break the dataset", "errors": rep.errors[:20]})
    ds = Dataset(candidate)
    used = {r for _, _, r in STATE.assignment.values()}
    missing_rooms = used - set(ds.rooms)
    if missing_rooms:
        raise HTTPException(409, {"message": f"rooms still used by the current timetable cannot be removed: {sorted(missing_rooms)}"})
    STATE.live_raw = candidate
    STATE.data_modified = True
    synced = set(STATE.assignment) == set(ds.sessions)
    if STATE.assignment and synced:
        STATE.validate()                      # re-check the existing timetable against the edited data
    elif STATE.assignment:
        STATE.last_validation, STATE.approved = None, False     # sessions changed: timetable is a draft until regenerated
    STATE.approved = STATE.approved and (STATE.last_validation or {}).get("accepted", False)
    STATE.save()
    audit.record(user.id, f"data.{what}", what, {})


def _coll(entity: str) -> str:
    if entity not in ENTITY:
        raise HTTPException(404, f"unknown entity; choose from {list(ENTITY)}")
    return ENTITY[entity]


@router.get("/admin/data/{entity}")
def list_entities(entity: str, user: User = Depends(admin)):
    return {"entity": entity, "items": STATE.live_raw[_coll(entity)], "modified_since_import": STATE.data_modified}


@router.post("/admin/data/{entity}", status_code=201)
def create_entity(entity: str, body: dict, user: User = Depends(admin)):
    c = _coll(entity)
    if not body.get("id"):
        raise HTTPException(422, "an 'id' is required")
    cand = copy.deepcopy(STATE.live_raw)
    if any(x["id"] == body["id"] for x in cand[c]):
        raise HTTPException(409, f"{body['id']} already exists")
    cand[c].append(body)
    _commit(cand, user, f"{entity}.create")
    return body


@router.put("/admin/data/{entity}/{item_id}")
def update_entity(entity: str, item_id: str, body: dict, user: User = Depends(admin)):
    c = _coll(entity)
    cand = copy.deepcopy(STATE.live_raw)
    for i, x in enumerate(cand[c]):
        if x["id"] == item_id:
            cand[c][i] = {**body, "id": item_id}
            _commit(cand, user, f"{entity}.update")
            return cand[c][i]
    raise HTTPException(404, f"{item_id} not found")


@router.delete("/admin/data/{entity}/{item_id}")
def delete_entity(entity: str, item_id: str, user: User = Depends(admin)):
    c = _coll(entity)
    cand = copy.deepcopy(STATE.live_raw)
    n = len(cand[c])
    cand[c] = [x for x in cand[c] if x["id"] != item_id]
    if len(cand[c]) == n:
        raise HTTPException(404, f"{item_id} not found")
    if c == "rooms" and any(r == item_id for _, _, r in STATE.assignment.values()):
        users = sorted(sid for sid, (_, _, r) in STATE.assignment.items() if r == item_id)
        raise HTTPException(409, {"message": f"{item_id} is used by {len(users)} scheduled session(s); move them first", "sessions": users[:20]})
    _commit(cand, user, f"{entity}.delete")
    return {"deleted": item_id}


@router.get("/admin/export/dataset")
def export_dataset(user: User = Depends(admin)):
    audit.record(user.id, "data.export", "dataset", {})
    return STATE.live_raw


@router.post("/admin/import/dataset")
def import_dataset_file(body: dict, user: User = Depends(admin)):
    """Load a dataset in the starter-pack JSON format (integrity-checked before anything is replaced)."""
    if len(json.dumps(body)) > 5_000_000:
        raise HTTPException(413, "file too large")
    rep = check_integrity(body)
    if not rep.ok:
        raise HTTPException(422, {"message": "file failed integrity checks; nothing was loaded", "errors": rep.errors[:30]})
    STATE.live_raw = body
    STATE.data_modified = True
    STATE.assignment, STATE.exams, STATE.outcome, STATE.last_validation, STATE.approved = {}, None, None, None, False
    STATE.save()
    audit.record(user.id, "data.import", "dataset", {"counts": rep.counts})
    return {"loaded": True, "counts": rep.counts, "next": "Generate a timetable for the new data."}
