"""CP-SAT timetable solver.

Decision: x[s,d,p,r] = session s runs on day d, starting period p, in room r.

HARD constraints (H1-H12, H14 of the official validator) are modelled as hard constraints and can
never be traded against soft penalties. Soft penalties S1-S6 reproduce the validator's formulas, so the
CP-SAT objective equals the validator's soft_total for the schedule it returns.

The same model powers minimum-disruption repair: pass `baseline` and a `move_weight` and the objective
becomes   move_weight * (#sessions not at their baseline day/period/room) + soft penalty.

The solver never reports UNKNOWN/FEASIBLE as OPTIMAL; the raw CP-SAT status is returned.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from ortools.sat.python import cp_model

from app.services.dataset.loader import KIND_TO_USE, LAST_TEACHING, Dataset
from app.services.scheduling.scoring import soft_penalties

log = logging.getLogger("campusx.solver")

Assignment = dict[str, tuple[str, int, str]]  # session_id -> (day, start_period, room_id)

# Constraint families, used for infeasibility diagnosis (assumption literals).
FAMILIES = ("H2_faculty", "H3_group", "H4_room", "H11_basket", "H12_daily_limit")


@dataclass
class SolveResult:
    status: str                       # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN | MODEL_INVALID | NO_CANDIDATES
    assignment: Assignment = field(default_factory=dict)
    objective: float | None = None
    best_bound: float | None = None
    soft_model: dict[str, int] = field(default_factory=dict)   # penalties as computed by the model
    moved: int | None = None
    wall_time_s: float = 0.0
    stats: dict[str, Any] = field(default_factory=dict)
    diagnosis: dict[str, Any] = field(default_factory=dict)    # filled when infeasible / no candidates

    @property
    def has_solution(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")


# ----------------------------------------------------------------------------- candidates
def build_candidates(ds: Dataset, *, enforce_allowed_uses: bool = True,
                     sessions: Iterable[str] | None = None
                     ) -> tuple[dict[str, list[tuple[str, int, str]]], dict[str, dict[str, int]]]:
    """Candidate (day, start, room) triples per session plus a per-session elimination breakdown.

    Every filter mirrors a validator rule (H5-H10, H14) so that a candidate can only violate the
    *pairwise* rules (overlaps, baskets, daily limit), which the model enforces separately.
    """
    cands: dict[str, list[tuple[str, int, str]]] = {}
    why: dict[str, dict[str, int]] = {}
    sids = list(sessions) if sessions is not None else list(ds.sessions)
    for sid in sids:
        s = ds.sessions[sid]
        elim: dict[str, int] = defaultdict(int)
        fac = s["faculty_id"]
        rooms_ok: list[str] = []
        for rid, r in ds.rooms.items():
            if r["type"] not in s["room_types"]:
                elim["room_type"] += 1
            elif r["capacity"] < s["size"]:
                elim["capacity"] += 1
            elif s.get("needs_accessible") and not r["accessible"]:
                elim["accessibility"] += 1
            elif enforce_allowed_uses and KIND_TO_USE[s["kind"]] not in r["allowed_uses"]:
                elim["allowed_uses"] += 1
            else:
                rooms_ok.append(rid)
        fx = s.get("fixed_slot")
        out: list[tuple[str, int, str]] = []
        for d in ds.days:
            for p in range(1, LAST_TEACHING + 1):
                if not ds.valid_start(s, p):
                    elim["period_rules(lunch/lab/bounds)"] += 1
                    continue
                if fx and (fx["day"] != d or fx["start_period"] != p):
                    elim["fixed_slot"] += 1
                    continue
                per = ds.periods(p, s["duration"])
                if any((d, q) in ds.fac_unavail[fac] for q in per):
                    elim["faculty_unavailable"] += 1
                    continue
                for rid in rooms_ok:
                    if any((d, q) in ds.room_unavail.get(rid, ()) for q in per):
                        elim["room_unavailable"] += 1
                        continue
                    out.append((d, p, rid))
        cands[sid] = out
        why[sid] = dict(elim)
    return cands, why


# ----------------------------------------------------------------------------- model
class TimetableModel:
    def __init__(self, ds: Dataset, *, baseline: Assignment | None = None, move_weight: int = 0,
                 pinned: Assignment | None = None, enforce_allowed_uses: bool = True, time_move_weight: int = 0,
                 family_literals: bool = False, preferred_free: dict | None = None):
        self.ds = ds
        self.baseline = baseline or {}
        self.move_weight = move_weight
        self.time_move_weight = time_move_weight
        self.time_moved_terms: list[Any] = []
        self.pinned = pinned or {}
        self.m = cp_model.CpModel()
        self.family_lits: dict[str, Any] = {}
        self.use_family_lits = family_literals
        self.cands, self.elim = build_candidates(ds, enforce_allowed_uses=enforce_allowed_uses)
        self.x: dict[str, dict[tuple[str, int, str], Any]] = {}
        self.T: dict[str, dict[tuple[str, int], Any]] = {}
        self.obj_terms: list[Any] = []
        self.soft_exprs: dict[str, list[Any]] = defaultdict(list)
        self.moved_terms: list[Any] = []
        self.empty_sessions = [sid for sid, c in self.cands.items() if not c]
        self.preferred_free = preferred_free or {}
        if not self.empty_sessions:
            self._build()

    # -- helpers
    def _enforce(self, ct, family: str):
        if self.use_family_lits:
            lit = self.family_lits.setdefault(family, self.m.NewBoolVar(f"fam_{family}"))
            ct.OnlyEnforceIf(lit)
        return ct

    def _occ_terms(self, sid: str, d: str, q: int) -> list[Any]:
        """T variables of session sid whose block covers (d, q)."""
        dur = self.ds.sessions[sid]["duration"]
        return [self.T[sid][(d, p)] for p in range(q - dur + 1, q + 1) if (d, p) in self.T[sid]]

    def _build(self) -> None:
        ds, m = self.ds, self.m
        sessions = ds.sessions
        # H1 + candidate variables
        for sid, cl in self.cands.items():
            xs = {}
            for (d, p, r) in cl:
                xs[(d, p, r)] = m.NewBoolVar(f"x_{sid}_{d}_{p}_{r}")
            self.x[sid] = xs
            m.AddExactlyOne(xs.values())
            tv: dict[tuple[str, int], Any] = {}
            by_time: dict[tuple[str, int], list[Any]] = defaultdict(list)
            for (d, p, r), v in xs.items():
                by_time[(d, p)].append(v)
            for key, vs in by_time.items():
                t = m.NewBoolVar(f"T_{sid}_{key[0]}_{key[1]}")
                m.Add(sum(vs) == t)
                tv[key] = t
            self.T[sid] = tv
            if sid in self.pinned:
                m.Add(xs[self.pinned[sid]] == 1) if self.pinned[sid] in xs else m.Add(0 == 1)

        # H4 room overlap
        room_slot: dict[tuple[str, str, int], list[Any]] = defaultdict(list)
        for sid, xs in self.x.items():
            dur = sessions[sid]["duration"]
            for (d, p, r), v in xs.items():
                for q in range(p, p + dur):
                    room_slot[(r, d, q)].append(v)
        for terms in room_slot.values():
            if len(terms) > 1:
                self._enforce(m.Add(sum(terms) <= 1), "H4_room")

        # H2 faculty overlap + H12 daily limit
        by_fac: dict[str, list[str]] = defaultdict(list)
        for sid, s in sessions.items():
            by_fac[s["faculty_id"]].append(sid)
        for fid, sids in by_fac.items():
            for d in ds.days:
                for q in range(1, LAST_TEACHING + 1):
                    terms = [t for sid in sids for t in self._occ_terms(sid, d, q)]
                    if len(terms) > 1:
                        self._enforce(m.Add(sum(terms) <= 1), "H2_faculty")
                mx = ds.faculty[fid].get("max_hours_per_day", 4)
                load = [sessions[sid]["duration"] * t for sid in sids for (dd, p), t in self.T[sid].items() if dd == d]
                if sum(sessions[sid]["duration"] for sid in sids) > mx and load:
                    self._enforce(m.Add(sum(load) <= mx), "H12_daily_limit")

        # H11 baskets: identical (day, period) for every member
        baskets: dict[str, list[str]] = defaultdict(list)
        for sid, s in sessions.items():
            if s.get("basket_slot"):
                baskets[s["basket_slot"]].append(sid)
        for b, sids in baskets.items():
            first = sids[0]
            allkeys = set().union(*[set(self.T[sid]) for sid in sids])
            for key in allkeys:
                for sid in sids[1:]:
                    a = self.T[first].get(key)
                    c = self.T[sid].get(key)
                    if a is None and c is None:
                        continue
                    if a is None:
                        self._enforce(m.Add(c == 0), "H11_basket")
                    elif c is None:
                        self._enforce(m.Add(a == 0), "H11_basket")
                    else:
                        self._enforce(m.Add(a == c), "H11_basket")

        # H3 group overlap (basket sessions are one key) + group occupancy for soft terms
        group_keys: dict[str, dict[str, str]] = defaultdict(dict)  # g -> key -> representative sid
        for sid, s in sessions.items():
            key = s.get("basket_slot") or sid
            for g in s["groups"]:
                group_keys[g].setdefault(key, sid)
        self.occ_g: dict[tuple[str, str, int], Any] = {}
        for g, keymap in group_keys.items():
            for d in ds.days:
                for q in range(1, LAST_TEACHING + 1):
                    terms = [t for rep in keymap.values() for t in self._occ_terms(rep, d, q)]
                    if len(terms) > 1:
                        self._enforce(m.Add(sum(terms) <= 1), "H3_group")
                    ov = m.NewBoolVar(f"occ_{g}_{d}_{q}")
                    if terms:
                        m.Add(sum(terms) == ov)
                    else:
                        m.Add(ov == 0)
                    self.occ_g[(g, d, q)] = ov
        self.group_keys = group_keys
        self._build_objective()

    # -- objective (validator-equivalent soft penalties)
    def _build_objective(self) -> None:
        ds, m = self.ds, self.m
        sessions = ds.sessions
        # S1 / S5 / S6 are per-candidate costs
        for sid, xs in self.x.items():
            s = sessions[sid]
            prefs = [p for p in ds.faculty[s["faculty_id"]].get("preferences", []) if p.get("type") == "avoid"]
            for (d, p, r), v in xs.items():
                per = ds.periods(p, s["duration"])
                s1 = 0
                for pref in prefs:
                    if d in pref.get("days", ds.days):
                        s1 += 2 * sum(1 for q in per if q in pref["periods"])
                if s1:
                    self.soft_exprs["S1"].append(s1 * v)
                room = ds.rooms[r]
                if room["capacity"] and s["size"] / room["capacity"] < 0.4:
                    self.soft_exprs["S5"].append(v)
                if LAST_TEACHING in per:
                    self.soft_exprs["S6"].append(v)
        # S2 gaps per group/day (lunch is not a period, so P5->P6 is contiguous)
        for g in self.group_keys:
            for d in ds.days:
                occ = [self.occ_g[(g, d, q)] for q in range(1, LAST_TEACHING + 1)]
                before = [m.NewBoolVar(f"bef_{g}_{d}_{i}") for i in range(LAST_TEACHING)]
                after = [m.NewBoolVar(f"aft_{g}_{d}_{i}") for i in range(LAST_TEACHING)]
                for i in range(LAST_TEACHING):
                    if i > 0:
                        m.AddImplication(occ[i - 1], before[i])
                        m.AddImplication(before[i - 1], before[i])
                    else:
                        m.Add(before[i] == 0)
                    j = LAST_TEACHING - 1 - i
                    if j < LAST_TEACHING - 1:
                        m.AddImplication(occ[j + 1], after[j])
                        m.AddImplication(after[j + 1], after[j])
                    else:
                        m.Add(after[j] == 0)
                for i in range(LAST_TEACHING):
                    gap = m.NewBoolVar(f"gap_{g}_{d}_{i}")
                    m.Add(gap >= before[i] + after[i] - occ[i] - 1)
                    self.soft_exprs["S2"].append(gap)
        # S3 >6 hours/day for a group (basket counted once)
        for g, keymap in self.group_keys.items():
            for d in ds.days:
                hours = []
                for rep in keymap.values():
                    dur = sessions[rep]["duration"]
                    hours += [dur * t for (dd, p), t in self.T[rep].items() if dd == d]
                if sum(sessions[rep]["duration"] for rep in keymap.values()) > 6:
                    ex = m.NewIntVar(0, 9, f"s3_{g}_{d}")
                    m.Add(ex >= sum(hours) - 6)
                    self.soft_exprs["S3"].append(3 * ex)
        # S4 same-course lectures on the same day (non-basket, per group) and basket-course repeats
        per_gc: dict[tuple[str, str], list[str]] = defaultdict(list)
        for sid, s in sessions.items():
            if s["kind"] == "lecture" and not s.get("basket_slot"):
                for g in s["groups"]:
                    per_gc[(g, s["course_id"])].append(sid)
        for (g, c), sids in per_gc.items():
            if len(sids) < 2:
                continue
            for d in ds.days:
                cnt = sum(t for sid in sids for (dd, p), t in self.T[sid].items() if dd == d)
                ex = m.NewIntVar(0, len(sids), f"s4_{g}_{c}_{d}")
                m.Add(ex >= cnt - 1)
                self.soft_exprs["S4"].append(3 * ex)
        bc: dict[str, list[str]] = defaultdict(list)
        for sid, s in sessions.items():
            if s.get("basket_slot"):
                bc[s["course_id"]].append(sid)
        for c, sids in bc.items():
            if len(sids) < 2:
                continue
            for d in ds.days:
                cnt = sum(t for sid in sids for (dd, p), t in self.T[sid].items() if dd == d)
                ex = m.NewIntVar(0, len(sids), f"s4b_{c}_{d}")
                m.Add(ex >= cnt - 1)
                self.soft_exprs["S4"].append(3 * ex)
        # movement vs baseline (any change of day/period/room counts as moved: matches validator stability)
        if self.baseline and self.move_weight:
            for sid, xs in self.x.items():
                b = self.baseline.get(sid)
                if b is None:
                    continue
                keep = xs.get(tuple(b))
                mv = m.NewBoolVar(f"moved_{sid}")
                if keep is None:
                    m.Add(mv == 1)
                else:
                    m.Add(mv + keep == 1)
                self.moved_terms.append(mv)
                if self.time_move_weight:      # secondary: prefer a room-only change over a time-slot change
                    tkeep = self.T[sid].get((b[0], b[1]))
                    tm = m.NewBoolVar(f"tmoved_{sid}")
                    if tkeep is None:
                        m.Add(tm == 1)
                    else:
                        m.Add(tm + tkeep == 1)
                    self.time_moved_terms.append(tm)

    def soft_sum(self):
        return sum(sum(v) if v else 0 for v in self.soft_exprs.values())

    def set_objective(self) -> None:
        total = self.soft_sum()
        if self.moved_terms:
            total = total + self.move_weight * sum(self.moved_terms)
            if self.time_moved_terms:
                total = total + self.time_move_weight * sum(self.time_moved_terms)
        self.m.Minimize(total)


# ----------------------------------------------------------------------------- quick necessary conditions
def quick_infeasibility(ds: Dataset) -> dict[str, Any] | None:
    """Arithmetic necessary conditions that give a definitive, explainable INFEASIBLE without search.

    Faculty: weekly hours must fit under (daily limit, free periods) summed over the week.
    Returns a diagnosis dict, or None when no necessary condition is violated (the solver then decides).
    """
    bad: dict[str, dict[str, Any]] = {}
    need: dict[str, int] = defaultdict(int)
    for s in ds.sessions.values():
        need[s["faculty_id"]] += s["duration"]
    for fid, hours in need.items():
        mx = ds.faculty[fid].get("max_hours_per_day", 4)
        cap = sum(min(mx, sum(1 for p in range(1, LAST_TEACHING + 1) if (d, p) not in ds.fac_unavail[fid]))
                  for d in ds.days)
        if hours > cap:
            bad[fid] = {"weekly_hours_required": hours, "max_hours_available": cap, "daily_limit": mx}
    if not bad:
        return None
    return {"conflicting_constraint_families": ["H7_faculty_unavailability", "H12_daily_limit"],
            "reason": "A faculty member has more teaching hours than their daily limit and availability allow.",
            "faculty": bad}


# ----------------------------------------------------------------------------- driver
def _extract(model: TimetableModel, solver: cp_model.CpSolver) -> Assignment:
    out: Assignment = {}
    for sid, xs in model.x.items():
        for key, v in xs.items():
            if solver.Value(v):
                out[sid] = key
                break
    return out


def solve_timetable(ds: Dataset, *, seed: int = 42, time_limit_s: int = 120, workers: int = 1,
                    baseline: Assignment | None = None, move_weight: int = 0,
                    pinned: Assignment | None = None, hint: Assignment | None = None,
                    optimise: bool = True, feasibility_share: float = 0.4,
                    max_moved: int | None = None, log_progress: bool = False, time_move_weight: int = 0,
                    enforce_allowed_uses: bool = True) -> SolveResult:
    """Generate (or repair) a timetable.

    Phase 1 finds any hard-feasible schedule; phase 2 minimises (movement +) soft penalties, warm-started
    from phase 1. Returned status is the true CP-SAT status of the final phase.
    """
    t0 = time.time()
    model = TimetableModel(ds, baseline=baseline, move_weight=move_weight, pinned=pinned,
                           enforce_allowed_uses=enforce_allowed_uses, time_move_weight=time_move_weight)
    n_vars = sum(len(v) for v in model.x.values())
    stats: dict[str, Any] = {"sessions": len(ds.sessions), "x_variables": n_vars, "seed": seed,
                             "workers": workers, "time_limit_s": time_limit_s}
    if model.empty_sessions:
        diag = {
            "reason": "Some sessions have no placement that satisfies the per-session hard rules.",
            "sessions_without_candidates": {sid: model.elim[sid] for sid in model.empty_sessions},
        }
        return SolveResult("NO_CANDIDATES", wall_time_s=time.time() - t0, stats=stats, diagnosis=diag)

    if hint:
        for sid, key in hint.items():
            for k, v in model.x.get(sid, {}).items():
                model.m.AddHint(v, 1 if k == tuple(key) else 0)

    def make_solver(limit: float) -> cp_model.CpSolver:
        sv = cp_model.CpSolver()
        sv.parameters.max_time_in_seconds = max(1.0, limit)
        sv.parameters.num_search_workers = workers
        sv.parameters.random_seed = seed
        sv.parameters.log_search_progress = log_progress
        return sv

    qi = quick_infeasibility(ds)
    if qi:
        return SolveResult("INFEASIBLE", wall_time_s=time.time() - t0, stats=stats, diagnosis=qi)

    # ---- phase 1: feasibility
    phase1_budget = time_limit_s * (feasibility_share if optimise else 1.0)
    solver = make_solver(phase1_budget)
    status = solver.Solve(model.m)
    stats["phase1_status"] = solver.StatusName(status)
    stats["phase1_time_s"] = round(solver.WallTime(), 2)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        res = SolveResult(solver.StatusName(status), wall_time_s=time.time() - t0, stats=stats)
        if status == cp_model.INFEASIBLE:
            res.diagnosis = diagnose_infeasibility(ds, seed=seed)
        return res
    sol1 = _extract(model, solver)
    if not optimise:
        return SolveResult(solver.StatusName(status), sol1, None, None, soft_penalties(ds, sol1),
                           _moved(sol1, baseline), time.time() - t0, stats)

    # ---- phase 2: optimise from the phase-1 solution
    model.m.ClearHints()
    for sid, key in sol1.items():
        for k, v in model.x[sid].items():
            model.m.AddHint(v, 1 if k == key else 0)
    model.set_objective()
    if max_moved is not None and model.moved_terms:
        model.m.Add(sum(model.moved_terms) <= max_moved)
    solver = make_solver(time_limit_s - (time.time() - t0))
    status = solver.Solve(model.m)
    stats["phase2_status"] = solver.StatusName(status)
    stats["phase2_time_s"] = round(solver.WallTime(), 2)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sol = _extract(model, solver)
        return SolveResult(solver.StatusName(status), sol, solver.ObjectiveValue(), solver.BestObjectiveBound(),
                           soft_penalties(ds, sol), _moved(sol, baseline), time.time() - t0, stats)
    # Phase 2 produced nothing within budget: fall back to the phase-1 schedule and say so honestly.
    stats["note"] = "optimisation phase found no improvement within budget; returning feasibility solution"
    return SolveResult("FEASIBLE", sol1, None, None, soft_penalties(ds, sol1), _moved(sol1, baseline), time.time() - t0, stats)


def _moved(sol: Assignment, baseline: Assignment | None) -> int | None:
    if not baseline:
        return None
    return sum(1 for sid, v in sol.items() if sid in baseline and tuple(baseline[sid]) != tuple(v))


# ----------------------------------------------------------------------------- diagnosis
def diagnose_infeasibility(ds: Dataset, *, seed: int = 42, time_limit_s: int = 60) -> dict[str, Any]:
    """Explain an infeasible model: which constraint *families* conflict.

    Re-solves with each family guarded by an assumption literal and asks CP-SAT for a sufficient set.
    Family-level only (e.g. "faculty overlap + room overlap"), which is what an admin can act on.
    """
    out: dict[str, Any] = {}
    model = TimetableModel(ds, family_literals=True)
    if model.empty_sessions:
        return {"sessions_without_candidates": {sid: model.elim[sid] for sid in model.empty_sessions}}
    lits = list(model.family_lits.values())
    names = {id(v): k for k, v in model.family_lits.items()}
    model.m.AddAssumptions(lits)
    sv = cp_model.CpSolver()
    sv.parameters.max_time_in_seconds = time_limit_s
    sv.parameters.random_seed = seed
    sv.parameters.num_search_workers = 1
    st = sv.Solve(model.m)
    out["diagnosis_status"] = sv.StatusName(st)
    if st == cp_model.INFEASIBLE:
        core = sv.SufficientAssumptionsForInfeasibility()
        fam_by_index = {v.Index(): k for k, v in model.family_lits.items()}
        out["conflicting_constraint_families"] = sorted({fam_by_index[i] for i in core if i in fam_by_index})
        out["note"] = ("Per-session rules (room type, capacity, accessibility, availability, lunch/lab periods, "
                       "fixed slots) are always on; the listed families cannot all hold together.")
    elif st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        out["note"] = "Feasible once pairwise families are treated as assumptions; conflict lies elsewhere."
    return out


def to_schedule_sessions(assign: Assignment) -> list[dict[str, Any]]:
    return [{"session_id": sid, "day": d, "start_period": p, "room_id": r}
            for sid, (d, p, r) in sorted(assign.items())]


def from_schedule(schedule: dict[str, Any]) -> Assignment:
    return {e["session_id"]: (e["day"], e["start_period"], e["room_id"]) for e in schedule.get("sessions", [])}
