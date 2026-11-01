"""Faculty scheduling assistant endpoints. Drafting is read-only; submitting saves a PROPOSAL that only an Admin can apply."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.api.routes.bookings import _confirmed
from app.api.routes.disruptions import _fingerprint
from app.core.auth import User, require_roles
from app.models.db import DisruptionRecord, session_scope
from app.services.ai import faculty_assistant as fa
from app.services.audit import log as audit, notify
from app.state import STATE

router = APIRouter(prefix="/assistant")
faculty = require_roles("faculty")


def _build(user: User, text: str, choices):
    if not STATE.assignment:
        raise HTTPException(409, "no timetable yet")
    if not user.faculty_id:
        raise HTTPException(403, "your account is not linked to a faculty record")
    return fa.build(STATE.live_raw, STATE.schedule(), STATE.assignment, STATE.exams, _confirmed(),
                    STATE.outcome.session_overrides if STATE.outcome else [], user.faculty_id, text, choices)


def _public(r: dict) -> dict:
    p = r.get("proposal")
    if p:
        p = {k: v for k, v in p.items() if k != "schedule_after"}
    return {**{k: v for k, v in r.items() if k != "proposal"}, "proposal": p}


@router.post("/schedule-request")
def draft(body: dict, user: User = Depends(faculty)):
    """Natural language -> structured request -> validated alternatives. Nothing is saved or applied."""
    text = str(body.get("text", "")).strip()
    if not (5 <= len(text) <= 600):
        raise HTTPException(422, "describe the change in 5-600 characters")
    choices = {k: int(v) for k, v in (body.get("choices") or {}).items()}
    r = _build(user, text, choices)
    audit.record(user.id, "assistant.draft", "-", {"affected": len(r.get("alternatives", {})), "valid": bool(r.get("proposal") and r["proposal"]["feasible"])})
    # keep the older, simpler response keys for existing clients
    it = r["interpretation"]
    return {**_public(r), "draft": it["unavailable"], "source": "rules",
            "note": "This is only a draft. Nothing changes until you submit it and an Admin approves it."}


@router.post("/submit")
def submit(body: dict, user: User = Depends(faculty)):
    """Re-generates the proposal on the SERVER (never trusting client-sent schedules), re-validates it, and saves it for Admin approval."""
    text = str(body.get("text", "")).strip()
    if not (5 <= len(text) <= 600):
        raise HTTPException(422, "describe the change in 5-600 characters")
    choices = {k: int(v) for k, v in (body.get("choices") or {}).items()}
    r = _build(user, text, choices)
    p = r.get("proposal")
    if not p or not p["feasible"]:
        raise HTTPException(409, {"message": "no valid proposal to submit", "no_solution": r.get("no_solution"),
                                  "rejected_by_validator": (p or {}).get("rejected_by_validator"), "follow_up": r.get("follow_up")})
    did = f"DIS-{uuid.uuid4().hex[:8]}"
    moved = p["moved"]
    proposal = {"feasible": True, "kind": "faculty-assistant", "solver_status": "ASSISTANT",
                "minimality": f"{len(moved)} session(s) proposed to move by the faculty assistant; each alternative was checked against every hard rule and the whole result was accepted by the official validator.",
                "summary": {"moved": len(moved), "unchanged": len(STATE.assignment) - len(moved), "added": 0, "removed": 0,
                            "time_changed": sum(1 for m in moved if m["time_changed"])},
                "evidence": {"method": "candidate search over hard rules + official validator on the full schedule", "proven_minimum": False,
                             "moved_total": len(moved), "time_slot_changes": sum(1 for m in moved if m["time_changed"]),
                             "room_only_changes": sum(1 for m in moved if not m["time_changed"]), "unchanged": len(STATE.assignment) - len(moved)},
                "moved": moved, "added": [], "removed": [], "affected": p["affected"], "exam_room_changes": [], "booking_changes": [],
                "validation": p["validation"], "baseline_fingerprint": _fingerprint(), "schedule_after": p["schedule_after"],
                "soft_before": (STATE.last_validation or {}).get("soft_total"), "soft_after": p["validation"]["soft_total"], "request_text": text}
    with session_scope() as s:
        s.add(DisruptionRecord(id=did, changes={"changes": p["changes"]}, status="previewed", proposal=proposal, requested_by=user.id))
        msg = f"{user.name} asked to change {len(moved)} session(s) ({did}). Review the proposal."
        notify.notify("role:admin", msg, "disruption", "/app/disruptions", sender=user.id, related_id=did, dedupe=f"dis:{did}:admin", session=s)
        if user.department:
            notify.notify(f"coord:{user.department}", msg, "disruption", "/app/disruptions", sender=user.id, related_id=did, dedupe=f"dis:{did}:coord", session=s)
    audit.record(user.id, "assistant.submit", did, {"moved": len(moved)})
    return {"id": did, "status": "previewed", "message": "Submitted for Admin approval. The timetable is unchanged until it is approved.", "moved": moved}
