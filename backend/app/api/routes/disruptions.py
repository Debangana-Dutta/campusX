"""Disruptions: preview a minimum-movement repair, show the exact diff, apply only after an Admin approves."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.auth import User, current_user, require_roles
from app.models.db import DisruptionRecord, session_scope
from app.schemas.api import DisruptionIn
from app.services.audit import log as audit
from app.services.bookings.engine import BookingEngine
from app.services.dataset.loader import Dataset, apply_disruption
from app.services.pipeline import apply_change_and_export
from app.services.scheduling.solver import from_schedule
from app.services.validation.runner import run_validator_on_dataset
from app.state import STATE, LOCK

router = APIRouter(prefix="/disruptions")


def _fingerprint() -> str:
    return hashlib.sha256(json.dumps(sorted((k, list(v)) for k, v in STATE.assignment.items())).encode()).hexdigest()[:16]


@router.get("")
def list_disruptions(user: User = Depends(current_user)):
    with session_scope() as s:
        return {"disruptions": [{"id": d.id, "status": d.status, "requested_by": d.requested_by, "approved_by": d.approved_by,
                                 "moved": (d.proposal or {}).get("summary", {}).get("moved"),
                                 "created_at": d.created_at.isoformat()} for d in s.scalars(select(DisruptionRecord))]}


@router.post("/preview")
def preview(body: DisruptionIn, user: User = Depends(require_roles("admin", "faculty", "department_coordinator"))):
    if not STATE.assignment:
        raise HTTPException(409, "generate a timetable first")
    if user.role == "faculty":
        for ch in body.changes:
            if ch.get("type") != "faculty_unavailable" or ch.get("faculty_id") != user.faculty_id:
                raise HTTPException(403, "faculty may only mark their own unavailability")
    with LOCK:
        sched = STATE.schedule()
        res = apply_change_and_export(STATE.live_raw, {"changes": body.changes}, sched, team=STATE.st.team_name,
                                      seed=STATE.st.solver_seed, time_limit_s=body.time_limit_s)
    rep = res["repair"]
    did = f"DIS-{uuid.uuid4().hex[:8]}"
    if not rep.ok:
        proposal = {"feasible": False, "status": rep.status, "conflict": rep.conflict, "affected": rep.affected}
        with session_scope() as s:
            s.add(DisruptionRecord(id=did, changes={"changes": body.changes}, status="infeasible", proposal=proposal,
                                   requested_by=user.id))
        audit.record(user.id, "disruption.preview", did, {"feasible": False})
        return {"id": did, **proposal}
    after = res["schedule_after"]
    v = run_validator_on_dataset(rep.new_raw, after, baseline=sched)
    summ = v.summary()
    before_dec = {d.request_id: d for d in (STATE.outcome.decisions if STATE.outcome else [])}
    booking_changes = [{"request_id": d.request_id, "before": before_dec[d.request_id].status, "after": d.status,
                        "reason": d.reason} for d in res["outcome"].decisions
                       if d.request_id in before_dec and (before_dec[d.request_id].status != d.status
                       or (before_dec[d.request_id].room_id, before_dec[d.request_id].day, before_dec[d.request_id].start_period)
                       != (d.room_id, d.day, d.start_period))]
    proposal = {"feasible": True, "solver_status": rep.status, "minimality": rep.minimality,
                "summary": {"moved": len(rep.moved), "unchanged": len(rep.unchanged), "added": len(rep.added),
                            "removed": len(rep.removed), "time_changed": sum(1 for m in rep.moved if m["time_changed"])},
                "moved": rep.moved, "added": rep.added, "removed": rep.removed, "affected": rep.affected,
                "exam_room_changes": res["exam_changes"], "booking_changes": booking_changes,
                "validation": summ, "baseline_fingerprint": _fingerprint(), "schedule_after": after,
                "soft_before": (STATE.last_validation or {}).get("soft_total"), "soft_after": summ["soft_total"]}
    status = "previewed" if summ["accepted"] else "invalid"
    with session_scope() as s:
        s.add(DisruptionRecord(id=did, changes={"changes": body.changes}, status=status, proposal=proposal, requested_by=user.id))
    audit.record(user.id, "disruption.preview", did, {"feasible": True, "moved": len(rep.moved), "accepted": summ["accepted"]})
    return {"id": did, "status": status, **{k: v for k, v in proposal.items() if k != "schedule_after"}}


@router.get("/{did}/comparison")
def comparison(did: str, user: User = Depends(current_user)):
    with session_scope() as s:
        d = s.get(DisruptionRecord, did)
        if not d:
            raise HTTPException(404, "unknown disruption")
        p = {k: v for k, v in (d.proposal or {}).items() if k != "schedule_after"}
        return {"id": d.id, "status": d.status, "requested_by": d.requested_by, "approved_by": d.approved_by,
                "changes": d.changes, "proposal": p}


@router.post("/apply")
def apply(did: str, user: User = Depends(require_roles("admin"))):
    """Admin approval step. Re-validates with the official validator before anything changes."""
    with LOCK, session_scope() as s:
        d = s.get(DisruptionRecord, did)
        if not d:
            raise HTTPException(404, "unknown disruption")
        if d.status != "previewed":
            raise HTTPException(409, f"disruption is '{d.status}', only a validated preview can be applied")
        if d.requested_by == user.id and d.requested_by != "admin":
            pass  # admin-initiated change files are approved by the same admin office (documented)
        p = d.proposal
        if p["baseline_fingerprint"] != _fingerprint():
            raise HTTPException(409, "the timetable changed since this preview; preview again")
        new_raw = apply_disruption(STATE.live_raw, d.changes)
        after = p["schedule_after"]
        v = run_validator_on_dataset(new_raw, after, baseline=STATE.schedule())
        if not v.accepted:
            raise HTTPException(409, {"message": "official validator rejected the proposal; nothing applied",
                                      "validation": v.summary()})
        STATE.live_raw = new_raw
        STATE.assignment = from_schedule(after)
        STATE.exams = after.get("exams")
        STATE.outcome = BookingEngine(Dataset(new_raw), STATE.assignment).decide()
        STATE.applied_disruptions.append({"id": did, "changes": d.changes})
        d.status, d.approved_by = "applied", user.id
        STATE.validate()
        audit.record(user.id, "disruption.apply", did, {"moved": p["summary"]["moved"]})
        return {"applied": True, "id": did, "validation": STATE.last_validation}
