"""Orchestration: timetable + exams + Spectra bookings -> official schedule.json, and disruption -> schedule_after.json.

Nothing is exported as 'accepted' unless the official validator accepts it (see ExportGate).
"""
from __future__ import annotations

import copy
from typing import Any

from app.services.bookings.engine import BookingEngine, BookingOutcome
from app.services.dataset.loader import Dataset
from app.services.disruptions.repair import RepairResult, repair_timetable
from app.services.exams.scheduler import ExamResult, room_closed_for_slot, schedule_exams
from app.services.scheduling.solver import Assignment, to_schedule_sessions
from app.services.validation.runner import ValidationResult, run_validator, run_validator_on_dataset


def assemble_schedule(team: str, dataset_id: str, assign: Assignment, outcome: BookingOutcome | None,
                      exams: list[dict] | None) -> dict[str, Any]:
    sched: dict[str, Any] = {"team": team, "dataset_id": dataset_id, "sessions": to_schedule_sessions(assign)}
    if outcome is not None:
        sched["fest_week"] = outcome.export()
    if exams is not None:
        sched["exams"] = exams
    return sched


def fix_exam_rooms(ds: Dataset, exams_out: list[dict]) -> tuple[list[dict], list[dict]]:
    """Replace rooms that are now closed, keeping each exam's day/session. Returns (exams, changes).

    If an exam cannot be re-roomed inside its slot it is left unchanged and reported; the caller then
    falls back to a full exam re-solve.
    """
    cal = ds.raw["calendar"]["exam_week"]
    slot_def = {s["id"]: s for s in cal["sessions"]}
    exam_rooms = {rid: r for rid, r in ds.rooms.items() if "exam" in r["allowed_uses"]}
    out = copy.deepcopy(exams_out)
    changes, failed = [], []
    used: dict[tuple, set] = {}
    for e in out:
        used.setdefault((e["day"], e["session"]), set()).update(e["rooms"])
    for e in out:
        slot = (e["day"], e["session"])
        bad = [r for r in e["rooms"] if room_closed_for_slot(ds, r, e["day"], slot_def[e["session"]])]
        if not bad:
            continue
        keep = [r for r in e["rooms"] if r not in bad]
        for r in bad:
            used[slot].discard(r)
        seats = sum(exam_rooms[r]["capacity"] // 2 for r in keep)
        need = ds.exams[e["exam_id"]]["size"]
        free = sorted((r for r in exam_rooms if r not in used[slot]
                       and not room_closed_for_slot(ds, r, e["day"], slot_def[e["session"]])),
                      key=lambda r: -exam_rooms[r]["capacity"])
        for r in free:
            if seats >= need:
                break
            keep.append(r)
            seats += exam_rooms[r]["capacity"] // 2
        if seats < need:
            failed.append(e["exam_id"])
            for r in bad:
                used[slot].add(r)
            continue
        used[slot].update(keep)
        changes.append({"exam_id": e["exam_id"], "removed_rooms": bad, "rooms": sorted(keep)})
        e["rooms"] = sorted(keep)
    if failed:
        return exams_out, [{"unresolved": failed}]
    return out, changes


def apply_change_and_export(raw: dict, disruption: dict, schedule: dict, *, team: str, seed: int,
                            time_limit_s: int) -> dict[str, Any]:
    """Repair the timetable, re-room exams, re-decide Spectra bookings and validate with the official CLI."""
    from app.services.scheduling.solver import from_schedule
    baseline = from_schedule(schedule)
    rep: RepairResult = repair_timetable(raw, disruption, baseline, seed=seed, time_limit_s=time_limit_s)
    res: dict[str, Any] = {"repair": rep}
    if not rep.ok:
        return res
    new_ds = Dataset(rep.new_raw)
    exams = schedule.get("exams")
    exam_changes: list[dict] = []
    if exams is not None:
        exams, exam_changes = fix_exam_rooms(new_ds, exams)
        if exam_changes and "unresolved" in exam_changes[0]:
            er: ExamResult = schedule_exams(new_ds, seed=seed, time_limit_s=40)
            exams = er.exams if er.has_solution else exams
            exam_changes = [{"note": "exams re-solved (room closure could not be absorbed in-slot)"}]
    outcome = BookingEngine(new_ds, rep.assignment).decide()
    after = assemble_schedule(team, new_ds.raw["dataset_id"], rep.assignment, outcome, exams)
    res.update(schedule_after=after, outcome=outcome, exam_changes=exam_changes, new_ds=new_ds)
    return res


def validate_after(raw_path, disruption_path, after: dict, baseline: dict) -> ValidationResult:
    return run_validator(after, data_path=raw_path, disruption_path=disruption_path, baseline=baseline)
