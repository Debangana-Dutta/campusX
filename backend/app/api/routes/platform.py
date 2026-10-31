"""Notifications, Campus Buddy, admin dashboard/venues/users/demo-reset, analytics."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select

from app.config import get_settings
from app.core.auth import DEMO_USERS, ROLES, User, current_user, require_roles
from app.models.db import (BookingRecord, DisruptionRecord, Notification, NotificationRead, RoleAssignment, session_scope)
from app.services.ai import buddy, gemini
from app.services.audit import log as audit, notify
from app.services.dataset.loader import load_raw
from app.state import STATE

router = APIRouter()
staff = require_roles("admin", "faculty", "department_coordinator", "club_representative")
admin = require_roles("admin")


# ---------------------------------------------------------------- notifications
@router.get("/notifications")
def notifications(user: User = Depends(current_user)):
    return notify.list_for(user)


@router.post("/notifications/read")
def read(body: dict, user: User = Depends(current_user)):
    ids = body.get("ids")
    return {"marked": notify.mark_read(user, ids if isinstance(ids, list) else None)}


@router.post("/notifications/announce")
def announce(body: dict, user: User = Depends(admin)):
    msg = str(body.get("message", "")).strip()
    aud = body.get("audience", "all")
    if not (3 <= len(msg) <= 400):
        raise HTTPException(422, "message must be 3-400 characters")
    target = "*" if aud == "all" else f"role:{aud}"
    if aud != "all" and aud not in (*ROLES, "student"):
        raise HTTPException(422, "unknown audience")
    notify.notify(target, msg, "announcement", None)
    audit.record(user.id, "notification.announce", target, {"len": len(msg)})
    return {"sent": True, "audience": target}


# ---------------------------------------------------------------- campus buddy
@router.post("/buddy/ask")
def buddy_ask(body: dict, user: User = Depends(current_user)):
    q = str(body.get("question", "")).strip()
    if not (2 <= len(q) <= 400):
        raise HTTPException(422, "ask a question of 2-400 characters")
    if not STATE.imported or not STATE.assignment:
        return {"answer": "No timetable is available yet, so I can't answer from timetable data.", "intent": "none",
                "facts": {}, "ai_used": False, "ai_error": None}
    out = buddy.ask(q, user, STATE.ds, STATE.assignment, STATE.exams, STATE.applied_disruptions,
                    group_id=body.get("group_id"), faculty_id=body.get("faculty_id"))
    audit.record(user.id, "buddy.ask", out["intent"], {"ai_used": out["ai_used"]})
    return out


@router.get("/ai/status")
def ai_status(user: User = Depends(current_user)):
    return {"gemini_configured": gemini.configured(),
            "fallback": "deterministic rules (booking parser + Campus Buddy lookup) are used whenever Gemini is unavailable"}


# ---------------------------------------------------------------- venues
@router.get("/venues")
def venues(user: User = Depends(staff)):
    ds = STATE.ds
    book_by_room: dict[str, list] = defaultdict(list)
    for d in (STATE.outcome.decisions if STATE.outcome else []):
        if d.room_id and d.status in ("approved", "alternative_offered"):
            book_by_room[d.room_id].append({"request_id": d.request_id, "title": ds.requests[d.request_id]["title"],
                                            "status": d.status, "day": d.day, "from": d.start_period, "to": d.end_period})
    with session_scope() as s:
        for b in s.scalars(select(BookingRecord).where(BookingRecord.state == "confirmed")):
            dec = b.decision
            if dec.get("room_id"):
                book_by_room[dec["room_id"]].append({"request_id": b.id, "title": b.request["title"], "status": "confirmed",
                                                     "day": dec["day"], "from": dec["start_period"], "to": dec["end_period"]})
    closures: dict[str, list] = defaultdict(list)
    for u in ds.raw.get("room_unavailability", []):
        closures[u["room_id"]].append({"day": u["day"], "periods": u["periods"], "reason": u.get("reason", "")})
    teach = Counter()
    for sid, (d, p, r) in STATE.assignment.items():
        teach[r] += ds.sessions[sid]["duration"]
    return {"rooms": [{**{k: r[k] for k in ("id", "name", "building", "type", "capacity", "features", "accessible", "allowed_uses")},
                       "closures": closures.get(rid, []), "bookings": book_by_room.get(rid, []),
                       "teaching_hours": teach.get(rid, 0)} for rid, r in ds.rooms.items()]}


# ---------------------------------------------------------------- admin: dashboard, users, reset
@router.get("/admin/summary")
def summary(user: User = Depends(staff)):
    ds = STATE.ds if STATE.imported else None
    with session_scope() as s:
        user_bookings = list(s.scalars(select(BookingRecord)))
        dis = list(s.scalars(select(DisruptionRecord)))
    pending = [b for b in user_bookings if b.state == "proposed"]
    v = STATE.last_validation or {}
    decs = STATE.outcome.decisions if STATE.outcome else []
    out: dict[str, Any] = {
        "timetable_status": STATE.status(), "approved_by": STATE.approved_by, "source": STATE.source,
        "sessions_total": len(ds.sessions) if ds else 0, "sessions_scheduled": len(STATE.assignment),
        "validation": {"accepted": v.get("accepted"), "hard_violation_count": v.get("hard_violation_count"),
                       "soft_total": v.get("soft_total")} if v else None,
        "pending_bookings": len(pending), "user_bookings": len(user_bookings),
        "active_disruptions": len([d for d in dis if d.status == "previewed"]),
        "applied_disruptions": len(STATE.applied_disruptions),
        "exams_scheduled": len(STATE.exams or []), "exams_total": len(ds.exams) if ds else 0,
        "spectra": {"approved": sum(d.status == "approved" for d in decs), "alternative": sum(d.status == "alternative_offered" for d in decs),
                    "rejected": sum(d.status == "rejected" for d in decs)},
        "booking_score": (v.get("booking") or {}).get("booking_score"),
    }
    return out


@router.get("/reports/analytics")
def analytics(user: User = Depends(staff)):
    ds = STATE.ds
    if not STATE.assignment:
        raise HTTPException(409, "no timetable yet")
    per_day = Counter(d for d, p, r in STATE.assignment.values())
    fac = Counter()
    for sid in STATE.assignment:
        s = ds.sessions[sid]
        fac[s["faculty_id"]] += s["duration"]
    slots = Counter()
    for e in STATE.exams or []:
        slots[f"{e['day']} {e['session']}"] += len(e["rooms"])
    kinds = Counter(ds.sessions[sid]["kind"] for sid in STATE.assignment)
    return {"sessions_per_day": [{"day": d, "sessions": per_day.get(d, 0)} for d in ds.days],
            "faculty_workload": [{"faculty_id": f, "name": ds.faculty[f]["name"], "hours": h} for f, h in fac.most_common(15)],
            "session_kinds": dict(kinds),
            "exam_rooms_per_slot": [{"slot": k, "rooms_used": v} for k, v in sorted(slots.items())],
            "data_origin": "computed from the generated timetable, exam schedule and booking decisions"}


@router.get("/admin/users")
def users(user: User = Depends(admin)):
    st = get_settings()
    with session_scope() as s:
        ra = [{"user_id": r.user_id, "role": r.role, "granted_by": r.granted_by} for r in s.scalars(select(RoleAssignment))]
    return {"auth_mode": st.auth_mode,
            "note": ("LOCAL DEVELOPMENT AUTH: these are fixed demo accounts, not production identities"
                     if st.auth_mode == "local" else "Roles come from Supabase app_metadata; assignments below are recorded by this backend"),
            "accounts": [{"username": k, "role": v["role"], "name": v["name"], "department": v["department"]} for k, v in DEMO_USERS.items()]
            if st.auth_mode == "local" else [], "role_assignments": ra}


@router.post("/admin/role-assignments")
def assign_role(body: dict, user: User = Depends(admin)):
    uid, role = str(body.get("user_id", "")).strip(), body.get("role")
    if role not in ROLES:
        raise HTTPException(422, f"role must be one of {list(ROLES)}")
    if not uid or uid == user.id:
        raise HTTPException(403, "you cannot assign or change your own role")
    with session_scope() as s:
        s.add(RoleAssignment(user_id=uid, role=role, granted_by=user.id))
    audit.record(user.id, "role.assign", uid, {"role": role})
    return {"assigned": True}


@router.get("/admin/audit")
def audit_log(limit: int = 100, user: User = Depends(admin)):
    return {"events": audit.recent(min(limit, 300))}


@router.post("/admin/demo-reset")
def demo_reset(user: User = Depends(admin)):
    """Reset to a clean demo state: drops user bookings/disruptions/notifications and reloads the app's own validated export."""
    st = get_settings()
    with session_scope() as s:
        for m in (BookingRecord, DisruptionRecord, Notification, NotificationRead):
            s.execute(delete(m))
    STATE.import_dataset(reset=True)
    p = st.exports_dir / "schedule.json"
    loaded = False
    if p.exists():
        import json
        v = STATE.load_schedule(json.loads(p.read_text()), "loaded_export", approver="system (validated export)")
        loaded = v.accepted
    audit.record(user.id, "admin.demo_reset", "-", {"timetable_loaded": loaded})
    return {"reset": True, "timetable_loaded_from_export": loaded, "status": STATE.status()}


@router.get("/events")
def events(user: User = Depends(current_user)):
    """Campus events (approved/confirmed bookings). Titles and places only; no requester private data."""
    ds = STATE.ds
    out = []
    for d in (STATE.outcome.decisions if STATE.outcome else []):
        if d.room_id and d.status == "approved":
            out.append({"id": d.request_id, "title": ds.requests[d.request_id]["title"], "category": d.effective_category,
                        "room_id": d.room_id, "day": d.day, "from": d.start_period, "to": d.end_period})
    with session_scope() as s:
        for b in s.scalars(select(BookingRecord).where(BookingRecord.state == "confirmed")):
            dec = b.decision
            out.append({"id": b.id, "title": b.request["title"], "category": dec.get("effective_category", "club_event"),
                        "room_id": dec["room_id"], "day": dec["day"], "from": dec["start_period"], "to": dec["end_period"]})
    order = {d: i for i, d in enumerate(ds.days)}
    return {"events": sorted(out, key=lambda e: (order.get(e["day"], 9), e["from"]))}
