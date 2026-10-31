"""Run the official validator.py as a separate process and parse its --json report.

validator.py is never imported or modified. A zero exit code only means "the script ran";
acceptance additionally requires a parsed report with zero hard violations.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings


class ValidatorError(RuntimeError):
    pass


@dataclass
class ValidationResult:
    ran: bool
    exit_code: int
    stdout: str
    stderr: str
    report: dict[str, Any] = field(default_factory=dict)

    @property
    def hard_violation_count(self) -> int:
        return int(self.report.get("hard_violation_count", -1))

    @property
    def accepted(self) -> bool:
        """Officially accepted: ran OK, report present with required sections, zero hard violations."""
        r = self.report
        return (self.ran and self.exit_code == 0 and r.get("hard_violation_count") == 0
                and "soft_total" in r and "hard_violations" in r)

    def summary(self) -> dict[str, Any]:
        r = self.report
        out = {
            "accepted": self.accepted,
            "exit_code": self.exit_code,
            "hard_violation_count": r.get("hard_violation_count"),
            "hard_by_rule": r.get("hard_by_rule", {}),
            "soft_total": r.get("soft_total"),
            "soft_penalties": r.get("soft_penalties", {}),
            "warnings": r.get("warnings", []),
        }
        if "bookings" in r:
            b = r["bookings"]
            out["booking"] = {k: b.get(k) for k in (
                "booking_score", "booking_score_max_if_all_approved", "approved", "alternatives",
                "rejected", "session_overrides")}
            out["priority_inversions"] = b.get("priority_inversions", [])
        if "exam_soft_penalty" in r:
            out["exam_soft_penalty"] = r["exam_soft_penalty"]
        if "stability" in r:
            s = r["stability"]
            out["stability"] = {k: s.get(k) for k in ("sessions_moved", "time_changed", "room_only_changed")}
            out["moved_ids"] = s.get("moved_ids", [])
        out["hard_violations"] = r.get("hard_violations", [])[:100]
        return out


def run_validator(schedule: dict[str, Any] | Path, *, data_path: Path | None = None,
                  disruption_path: Path | None = None,
                  baseline: dict[str, Any] | Path | None = None,
                  timeout_s: int = 120) -> ValidationResult:
    st = get_settings()
    data_path = Path(data_path or st.dataset_path)
    validator = Path(st.validator_path)
    if not validator.exists():
        raise ValidatorError("official validator.py not found; check VALIDATOR_PATH")

    with tempfile.TemporaryDirectory(prefix="cx_val_") as tmp:
        tmpd = Path(tmp)

        def materialise(obj: dict | Path, name: str) -> Path:
            if isinstance(obj, Path):
                return obj
            p = tmpd / name
            p.write_text(json.dumps(obj), encoding="utf-8")
            return p

        sched_p = materialise(schedule, "schedule.json")
        report_p = tmpd / "report.json"
        cmd = [sys.executable, str(validator), "--data", str(data_path), "--schedule", str(sched_p),
               "--json", str(report_p), "--quiet"]
        if disruption_path:
            cmd += ["--disruption", str(disruption_path)]
        if baseline is not None:
            cmd += ["--baseline", str(materialise(baseline, "baseline.json"))]
        try:
            cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s,
                                cwd=str(validator.parent))
        except subprocess.TimeoutExpired as e:
            raise ValidatorError(f"validator timed out after {timeout_s}s") from e
        report: dict[str, Any] = {}
        if report_p.exists():
            try:
                report = json.loads(report_p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                report = {}
        return ValidationResult(ran=True, exit_code=cp.returncode, stdout=cp.stdout,
                                stderr=cp.stderr, report=report)


def run_validator_on_dataset(data: dict[str, Any], schedule: dict[str, Any], **kw) -> ValidationResult:
    """Validate against an in-memory dataset (e.g. after a disruption) by writing it to a temp file."""
    with tempfile.TemporaryDirectory(prefix="cx_data_") as tmp:
        p = Path(tmp) / "data.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return run_validator(schedule, data_path=p, **kw)
