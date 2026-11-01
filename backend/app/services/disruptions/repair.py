"""Minimum-disruption repair.

Objective (lexicographic, enforced by weights): 1) fewest sessions whose (day, period, room) changes
vs the baseline, 2) lowest soft penalty. Hard constraints are never relaxed.

Level 1 pins every still-valid baseline session and frees only the affected/added ones.
Level 2 frees everything, bounded by Level 1's result, to look for a schedule that moves fewer sessions
(possible when moving one unaffected session avoids moving several affected ones). The reported status
is the true CP-SAT status: only OPTIMAL for the movement objective supports a "minimum" claim.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.services.dataset.loader import Dataset, apply_disruption
from app.services.scheduling.scoring import soft_penalties
from app.services.scheduling.solver import Assignment, SolveResult, build_candidates, solve_timetable

# Soft penalty is bounded well below this (<= groups*days*periods gaps + small terms), so movement strictly dominates:
# the objective is lexicographic (fewest moved sessions first, then lowest soft penalty).
MOVE_WEIGHT = 100_000
TIME_WEIGHT = 100   # secondary: room-only moves preferred over time-slot moves (max 190*100 < MOVE_WEIGHT)


@dataclass
class RepairResult:
    status: str                                   # OPTIMAL | FEASIBLE | INFEASIBLE | NO_CANDIDATES | UNKNOWN
    ok: bool
    new_raw: dict[str, Any] = field(default_factory=dict)
    assignment: Assignment = field(default_factory=dict)
    moved: list[dict[str, Any]] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    added: list[dict[str, Any]] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    affected: dict[str, list[str]] = field(default_factory=dict)
    minimality: str = ""
    soft: dict[str, int] = field(default_factory=dict)
    conflict: dict[str, Any] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    wall_time_s: float = 0.0


def find_affected(old_ds: Dataset, new_ds: Dataset, baseline: Assignment) -> dict[str, list[str]]:
    """Baseline sessions whose current slot is no longer valid under the new data, with reasons."""
    out: dict[str, list[str]] = {}
    for sid, (d, p, r) in baseline.items():
        s = new_ds.sessions.get(sid)
        if s is None:
            continue
        reasons = []
        per = range(p, p + s["duration"])
        for q in per:
            if (d, q) in new_ds.fac_unavail[s["faculty_id"]] and (d, q) not in old_ds.fac_unavail.get(s["faculty_id"], set()):
                reasons.append(f"faculty {s['faculty_id']} newly unavailable {d} P{q}")
                break
        for q in per:
            if (d, q) in new_ds.room_unavail.get(r, ()) and (d, q) not in old_ds.room_unavail.get(r, set()):
                reasons.append(f"room {r} newly closed {d} P{q}")
                break
        if old_ds.sessions.get(sid) != s:
            reasons.append("session definition changed")
        if reasons:
            out[sid] = reasons
    return out


def repair_timetable(raw: dict[str, Any], disruption: dict[str, Any], baseline: Assignment, *,
                     seed: int = 42, time_limit_s: int = 120, workers: int = 1) -> RepairResult:
    t0 = time.time()
    old_ds = Dataset(raw)
    try:
        new_raw = apply_disruption(raw, disruption)
    except (ValueError, KeyError) as e:
        return RepairResult("INVALID_DISRUPTION", False, conflict={"error": str(e)})
    new_ds = Dataset(new_raw)

    removed = [sid for sid in baseline if sid not in new_ds.sessions]
    added_ids = [sid for sid in new_ds.sessions if sid not in baseline]
    base_kept: Assignment = {sid: tuple(v) for sid, v in baseline.items() if sid in new_ds.sessions}
    affected = find_affected(old_ds, new_ds, base_kept)

    # sessions that cannot be placed anywhere (per-session rules) -> immediate, explainable failure
    cands, why = build_candidates(new_ds)
    dead = {sid: why[sid] for sid, c in cands.items() if not c}
    if dead:
        return RepairResult("NO_CANDIDATES", False, new_raw=new_raw, removed=removed, affected=affected,
                            conflict={"reason": "Some sessions have no valid placement after the change.",
                                      "sessions": dead}, wall_time_s=time.time() - t0)

    free = set(affected) | set(added_ids)
    pinned = {sid: v for sid, v in base_kept.items() if sid not in free}
    # level 1: only affected + added sessions may move
    l1_budget = max(20, int(time_limit_s * 0.35))
    r1 = solve_timetable(new_ds, seed=seed, time_limit_s=l1_budget, workers=workers, baseline=base_kept,
                         move_weight=MOVE_WEIGHT, time_move_weight=TIME_WEIGHT, pinned=pinned, feasibility_share=0.5)
    best: SolveResult | None = r1 if r1.has_solution else None
    stats = {"level1_status": r1.status, "level1_moved": r1.moved, "level1_time_s": round(r1.wall_time_s, 1)}
    upper = (r1.moved if r1.has_solution else None)
    must_move = len(free & set(base_kept)) + 0  # affected sessions that must leave their slot

    # level 2: free everything, objective = movement then soft, bounded by level 1
    remaining = time_limit_s - (time.time() - t0)
    if remaining > 5:
        r2 = solve_timetable(new_ds, seed=seed, time_limit_s=int(remaining), workers=workers, baseline=base_kept,
                             move_weight=MOVE_WEIGHT, time_move_weight=TIME_WEIGHT, hint=(best.assignment if best else None),
                             max_moved=upper, feasibility_share=0.3)
        stats.update(level2_status=r2.status, level2_moved=r2.moved, level2_time_s=round(r2.wall_time_s, 1))
        if r2.has_solution and (best is None or (r2.moved or 0) <= (best.moved or 0)):
            best = r2
        elif not r2.has_solution and best is None:
            best = r2
    if best is None or not best.has_solution:
        conflict = dict(best.diagnosis) if best else {}
        conflict.setdefault("reason", "No timetable satisfies every hard constraint after this change.")
        conflict.setdefault("affected_sessions", affected)
        return RepairResult(best.status if best else "UNKNOWN", False, new_raw=new_raw, removed=removed,
                            affected=affected, conflict=conflict, stats=stats, wall_time_s=time.time() - t0)

    assign = best.assignment
    moved, unchanged = [], []
    for sid, new in sorted(assign.items()):
        if sid in base_kept:
            old = tuple(base_kept[sid])
            if old != tuple(new):
                if sid in affected:
                    reason = "; ".join(affected[sid])
                else:
                    reason = "moved to make room for displaced sessions (keeps total moves lowest)"
                moved.append({"session_id": sid, "from": {"day": old[0], "start_period": old[1], "room_id": old[2]},
                              "to": {"day": new[0], "start_period": new[1], "room_id": new[2]},
                              "reason": reason, "time_changed": old[:2] != tuple(new)[:2]})
            else:
                unchanged.append(sid)
    added = [{"session_id": sid, "placed": {"day": assign[sid][0], "start_period": assign[sid][1], "room_id": assign[sid][2]},
              "reason": "new session added by the change"} for sid in added_ids if sid in assign]
    n_moved = len(moved)
    forced = len([sid for sid in affected if sid in assign])
    final = best                       # the solve that produced the schedule
    full = stats.get("level2_status")
    proven = bool(final.status == "OPTIMAL" and (full == "OPTIMAL" or stats.get("level1_status") == "OPTIMAL" and not (final is not None and full)))
    # "proven" needs a solve over the FULL model (everything may move) that CP-SAT closed as OPTIMAL.
    proven = full == "OPTIMAL" and best.status == "OPTIMAL"
    time_changed = sum(1 for m in moved if m["time_changed"])
    evidence = {
        "method": "CP-SAT, objective = 100000 x (sessions whose day/period/room changed) + 100 x (of those, time-slot changes) + soft penalty; every session free to move",
        "solver_status": best.status, "full_model_status": full, "level1_status": stats.get("level1_status"),
        "objective": best.objective, "best_bound": best.best_bound, "moved_total": n_moved,
        "time_slot_changes": time_changed, "room_only_changes": n_moved - time_changed, "unchanged": len(unchanged),
        "directly_invalidated_lower_bound": forced, "proven_minimum": proven,
    }
    if proven:
        minimality = (f"Proven minimum: CP-SAT closed the full model as OPTIMAL (objective {best.objective:.0f} = bound {best.best_bound:.0f}); "
                      f"no valid timetable moves fewer than {n_moved} session(s) ({time_changed} time-slot, {n_moved - time_changed} room-only).")
    else:
        minimality = (f"{n_moved} session(s) moved ({time_changed} time-slot, {n_moved - time_changed} room-only); solver status {best.status} "
                      f"({forced} were directly invalidated). Not proven minimal within the time limit.")
    return RepairResult(best.status, True, new_raw, assign, moved, unchanged, added, removed, affected, minimality,
                        soft_penalties(new_ds, assign), {}, stats, evidence, time.time() - t0)
