"""Exam scheduling (CP-SAT).

Rules (verified against README + validator.check_exams):
  * exam week: calendar.exam_week.days x calendar.exam_week.sessions (AM/PM)
  * only rooms whose allowed_uses contains "exam" may be used
  * effective capacity = capacity // 2 (summed over all rooms of the exam must cover `size`)
  * a room hosts at most one exam per slot; a group sits at most one exam per slot (hard)
  * soft: a group with 2+ exams on one day costs 5 per extra exam (validator exam_soft_penalty)
Stricter than the validator (documented): rooms closed by room_unavailability during the exam clock window are
not used, so a closure announced by a disruption also protects exam week.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ortools.sat.python import cp_model

from app.services.dataset.loader import Dataset


def _hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


@dataclass
class ExamResult:
    status: str
    exams: list[dict[str, Any]] = field(default_factory=list)
    penalty: int | None = None
    wall_time_s: float = 0.0
    diagnosis: dict[str, Any] = field(default_factory=dict)

    @property
    def has_solution(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")


def room_closed_for_slot(ds: Dataset, room_id: str, day: str, slot: dict) -> bool:
    """True if any teaching period overlapping the exam clock window is unavailable for the room."""
    a, b = _hhmm(slot["start"]), _hhmm(slot["end"])
    for per in ds.raw["calendar"]["periods"]:
        if _hhmm(per["start"]) < b and a < _hhmm(per["end"]) and (day, per["id"]) in ds.room_unavail.get(room_id, ()):
            return True
    return False


def schedule_exams(ds: Dataset, *, seed: int = 42, time_limit_s: int = 40, respect_closures: bool = True) -> ExamResult:
    t0 = time.time()
    cal = ds.raw["calendar"]["exam_week"]
    slots = [(d, s["id"]) for d in cal["days"] for s in cal["sessions"]]
    slot_def = {s["id"]: s for s in cal["sessions"]}
    rooms = {rid: r for rid, r in ds.rooms.items() if "exam" in r["allowed_uses"]}
    exams = ds.exams
    if not exams:
        return ExamResult("OPTIMAL", [], 0, time.time() - t0)

    # quick necessary condition: biggest exam must fit all exam seats of a slot
    total_seats = sum(r["capacity"] // 2 for r in rooms.values())
    too_big = {eid: e["size"] for eid, e in exams.items() if e["size"] > total_seats}
    if too_big:
        return ExamResult("INFEASIBLE", diagnosis={
            "reason": "Exam larger than all exam-capable rooms combined at half capacity",
            "exams": too_big, "total_exam_seats_per_slot": total_seats})

    m = cp_model.CpModel()
    et = {(e, t): m.NewBoolVar(f"et_{e}_{t[0]}_{t[1]}") for e in exams for t in slots}
    z: dict[tuple, Any] = {}
    for e in exams:
        m.AddExactlyOne(et[(e, t)] for t in slots)
    for t in slots:
        for rid in rooms:
            closed = respect_closures and room_closed_for_slot(ds, rid, t[0], slot_def[t[1]])
            terms = []
            for e in exams:
                if closed:
                    continue
                v = m.NewBoolVar(f"z_{e}_{rid}_{t[0]}_{t[1]}")
                m.AddImplication(v, et[(e, t)])
                z[(e, rid, t)] = v
                terms.append(v)
            if len(terms) > 1:
                m.AddAtMostOne(terms)
    for e, ex in exams.items():
        for t in slots:
            seats = [(rooms[rid]["capacity"] // 2) * z[(e, rid, t)] for rid in rooms if (e, rid, t) in z]
            m.Add(sum(seats) >= ex["size"]).OnlyEnforceIf(et[(e, t)])
    by_group: dict[str, list[str]] = defaultdict(list)
    for e, ex in exams.items():
        for g in ex["groups"]:
            by_group[g].append(e)
    for g, es in by_group.items():
        for t in slots:
            if len(es) > 1:
                m.AddAtMostOne(et[(e, t)] for e in es)
    # soft: >1 exam per group per day
    pen_terms = []
    for g, es in by_group.items():
        for d in cal["days"]:
            cnt = sum(et[(e, (d, s["id"]))] for e in es for s in cal["sessions"])
            ex_ = m.NewIntVar(0, len(es), f"day_{g}_{d}")
            m.Add(ex_ >= cnt - 1)
            pen_terms.append(5 * ex_)
    rooms_used = sum(z.values()) if z else 0
    m.Minimize(100 * sum(pen_terms) + rooms_used)   # clashes first, then use as few rooms as possible

    sv = cp_model.CpSolver()
    sv.parameters.max_time_in_seconds = time_limit_s
    sv.parameters.random_seed = seed
    sv.parameters.num_search_workers = 1
    st = sv.Solve(m)
    name = sv.StatusName(st)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ExamResult(name, wall_time_s=time.time() - t0,
                          diagnosis={"reason": "no exam timetable satisfies room-seat and group-clash rules",
                                     "exam_rooms": len(rooms), "slots": len(slots)})
    out = []
    pen = 0
    for e in exams:
        for t in slots:
            if sv.Value(et[(e, t)]):
                used = sorted(rid for rid in rooms if (e, rid, t) in z and sv.Value(z[(e, rid, t)]))
                out.append({"exam_id": e, "day": t[0], "session": t[1], "rooms": used})
    gd: dict[tuple, set] = defaultdict(set)
    for x in out:
        for g in exams[x["exam_id"]]["groups"]:
            gd[(g, x["day"])].add(x["exam_id"])
    pen = sum(5 * (len(v) - 1) for v in gd.values() if len(v) > 1)
    return ExamResult(name, out, pen, time.time() - t0)
