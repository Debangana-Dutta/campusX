"""Application state: original dataset (read-only) + live data after applied disruptions + current schedule.

Original source files are never modified. Re-importing is idempotent: it re-reads the preserved file, re-runs the
integrity checks and replaces the in-memory/persisted *derived* state only when asked to reset.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.bookings.engine import BookingEngine, BookingOutcome, Decision
from app.services.dataset.loader import Dataset, IntegrityReport, check_integrity, load_raw, sha256_file
from app.services.exams.scheduler import schedule_exams
from app.services.pipeline import assemble_schedule
from app.services.scheduling.solver import Assignment, from_schedule, solve_timetable, to_schedule_sessions
from app.services.validation.runner import ValidationResult, run_validator_on_dataset

LOCK = threading.RLock()


class AppState:
    def __init__(self) -> None:
        self.st = get_settings()
        self.raw: dict[str, Any] = {}
        self.live_raw: dict[str, Any] = {}
        self.integrity: IntegrityReport | None = None
        self.assignment: Assignment = {}
        self.exams: list[dict] | None = None
        self.outcome: BookingOutcome | None = None
        self.solver_info: dict[str, Any] = {}
        self.last_validation: dict[str, Any] | None = None
        self.applied_disruptions: list[dict[str, Any]] = []
        self.imported = False
        self.approved = False
        self.data_modified = False
        self.exams_published = False
        self.approved_by: str | None = None
        self.source = "none"   # none | generated | loaded_export

    # ---- dataset
    @property
    def path(self) -> Path:
        return self.st.dataset_path

    @property
    def ds(self) -> Dataset:
        return Dataset(self.live_raw)

    def import_dataset(self, reset: bool = False) -> IntegrityReport:
        with LOCK:
            raw = load_raw(self.path)
            rep = check_integrity(raw)
            self.integrity = rep
            if not rep.ok:
                return rep                       # never load a dataset that fails integrity
            if reset or not self.imported:
                self.raw = raw
                self.live_raw = json.loads(json.dumps(raw))
                self.assignment, self.exams, self.outcome = {}, None, None
                self.applied_disruptions, self.solver_info, self.last_validation = [], {}, None
                self.imported = True
                self.data_modified = False
                self._restore_if_any(reset)
            return rep

    # ---- persistence of derived state
    def save(self) -> None:
        """Persist derived state in the database (survives restarts and redeploys when the DB is PostgreSQL)."""
        from app.models.db import KeyValue, session_scope
        data = {"assignment": {k: list(v) for k, v in self.assignment.items()}, "exams": self.exams,
                "decisions": [d.as_dict() for d in self.outcome.decisions] if self.outcome else None,
                "overrides": self.outcome.session_overrides if self.outcome else None,
                "solver_info": self.solver_info, "applied_disruptions": self.applied_disruptions,
                "live_raw": self.live_raw if (self.applied_disruptions or self.data_modified) else None,
                "last_validation": self.last_validation, "approved": self.approved,
                "approved_by": self.approved_by, "source": self.source, "exams_published": self.exams_published}
        with session_scope() as s:
            row = s.get(KeyValue, "state")
            if row:
                row.value = data
            else:
                s.add(KeyValue(key="state", value=data))

    def _restore_if_any(self, reset: bool) -> None:
        from app.models.db import KeyValue, session_scope
        with session_scope() as s:
            row = s.get(KeyValue, "state")
            if reset:
                if row:
                    s.delete(row)
                return
            d = row.value if row else None
        if not d:
            return
        try:
            self.assignment = {k: tuple(v) for k, v in (d.get("assignment") or {}).items()}
            self.exams = d.get("exams")
            self.solver_info = d.get("solver_info") or {}
            self.applied_disruptions = d.get("applied_disruptions") or []
            self.last_validation = d.get("last_validation")
            self.approved, self.approved_by, self.source = d.get("approved", False), d.get("approved_by"), d.get("source", "none")
            self.exams_published = d.get("exams_published", bool(self.exams))      # older saved states: exams were visible
            if d.get("live_raw"):
                self.live_raw = d["live_raw"]
                self.data_modified = True
            if d.get("decisions") is not None:
                decs = [Decision(x["request_id"], x["status"], x["reason"], x["effective_category"], x.get("day"),
                                 x.get("start_period"), x.get("end_period"), x.get("room_id"),
                                 x.get("displaced_sessions", []), x.get("requires_admin_approval", False), x.get("code", ""))
                        for x in d["decisions"]]
                self.outcome = BookingOutcome(decs, d.get("overrides") or [], dict(self.assignment))
        except Exception:  # noqa: BLE001  corrupt persisted state -> start clean rather than crash
            self.assignment, self.exams, self.outcome = {}, None, None

    # ---- schedule assembly / validation
    def schedule(self) -> dict[str, Any]:
        return assemble_schedule(self.st.team_name, self.live_raw["dataset_id"], self.assignment, self.outcome, self.exams)

    def validate(self, schedule: dict[str, Any] | None = None) -> ValidationResult:
        res = run_validator_on_dataset(self.live_raw, schedule or self.schedule())
        if schedule is None:
            self.last_validation = res.summary()
            self.save()
        return res

    def status(self) -> str:
        """draft | validated | approved | invalid  - 'approved' is only possible after official acceptance."""
        if not self.assignment:
            return "none"
        v = self.last_validation
        if v is None:
            return "draft"
        if not v.get("accepted"):
            return "invalid"
        return "approved" if self.approved else "validated"

    def approve(self, who: str) -> None:
        if not (self.last_validation or {}).get("accepted"):
            raise ValueError("cannot approve: the official validator has not accepted this schedule")
        self.approved, self.approved_by = True, who
        self.save()

    def load_schedule(self, schedule: dict, source: str, approver: str | None = None) -> ValidationResult:
        """Load a finished schedule (e.g. the app's own validated export). Re-validated before it is trusted."""
        with LOCK:
            ds = self.ds
            self.assignment = from_schedule(schedule)
            self.exams = schedule.get("exams")
            self.outcome = BookingEngine(ds, self.assignment).decide()
            self.source, self.approved, self.approved_by = source, False, None
            self.exams_published = bool(self.exams)       # a validated export loaded by the system is published; generated exams are not
            v = self.validate()
            if v.accepted and approver:
                self.approve(approver)
            self.save()
            return v

    # ---- generation
    def generate(self, *, seed: int, time_limit_s: int, include_exams: bool = True, include_bookings: bool = True,
                 hint_from_saved: bool = True) -> dict[str, Any]:
        with LOCK:
            ds = self.ds
            hint = self.assignment if (hint_from_saved and self.assignment and set(self.assignment) == set(ds.sessions)) else None
            if hint is None and hint_from_saved:
                # warm start from the last validated timetable the solver saved (still re-solved + re-validated here)
                seed_file = self.st.state_dir / "timetable_seed.json"
                if seed_file.exists():
                    saved = from_schedule({"sessions": json.loads(seed_file.read_text()).get("sessions", [])})
                    if set(saved) == set(ds.sessions):
                        hint = saved
            res = solve_timetable(ds, seed=seed, time_limit_s=time_limit_s, workers=self.st.solver_workers,
                                  hint=hint, feasibility_share=0.1 if hint else 0.4)
            info = {"status": res.status, "objective": res.objective, "best_bound": res.best_bound,
                    "soft_penalties": res.soft_model, "wall_time_s": round(res.wall_time_s, 1), "seed": seed,
                    "stats": res.stats, "diagnosis": res.diagnosis}
            if not res.has_solution:
                self.solver_info = info
                return {"ok": False, **info}
            self.assignment = res.assignment
            self.approved, self.approved_by, self.source = False, None, "generated"
            if include_exams:
                ex = schedule_exams(ds, seed=seed, time_limit_s=30)
                if not ex.has_solution:
                    self.solver_info = {**info, "exam_status": ex.status, "exam_diagnosis": ex.diagnosis}
                    return {"ok": False, **self.solver_info}
                self.exams = ex.exams
                self.exams_published = False             # new exams are a draft until an admin publishes them
                info["exam_status"] = ex.status
            if include_bookings:
                self.outcome = BookingEngine(ds, self.assignment).decide()
            self.solver_info = info
            v = self.validate()
            self.save()
            from app.models.db import record_version
            sm = v.summary()
            record_version("generated", res.status, v.accepted, sm["hard_violation_count"], sm["soft_total"],
                           self.schedule(), exam_status=info.get("exam_status"))
            return {"ok": True, "validation": v.summary(), **info, "accepted": v.accepted}


STATE = AppState()
