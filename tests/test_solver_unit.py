"""Isolated solver unit tests on TINY SYNTHETIC datasets (tests/synthetic.py). Not official data."""
import pytest

from app.services.dataset.loader import Dataset
from app.services.scheduling.solver import build_candidates, solve_timetable
from synthetic import make, session


def solve(raw, **kw):
    return solve_timetable(Dataset(raw), time_limit_s=20, **kw)


def test_fixed_slot_respected():
    s = session("S1", fixed={"day": "THU", "start_period": 7})
    r = solve(make([s]))
    assert r.has_solution and r.assignment["S1"][:2] == ("THU", 7)


def test_lab_only_starts_p2_or_p6_and_never_crosses_lunch():
    s = session("LAB", kind="lab", dur=3, types=("lab_cs",))
    ds = Dataset(make([s]))
    c, _ = build_candidates(ds)
    assert {p for (_, p, _) in c["LAB"]} == {2, 6}


def test_faculty_daily_limit_enforced():
    # FA may teach 2h/day; three 1h sessions of FA for different groups must land on >=2 days
    ss = [session(f"S{i}", faculty="FA", groups=("G1" if i % 2 else "G2",)) for i in range(3)]
    r = solve(make(ss))
    assert r.has_solution
    per_day = {}
    for sid, (d, p, rm) in r.assignment.items():
        per_day[d] = per_day.get(d, 0) + 1
    assert max(per_day.values()) <= 2


def test_basket_sessions_synchronised_in_different_rooms():
    ss = [session("B1", faculty="FA", basket="OEB", groups=("G1", "G2")),
          session("B2", faculty="FB", basket="OEB", groups=("G1", "G2"))]
    r = solve(make(ss))
    assert r.has_solution
    (d1, p1, r1), (d2, p2, r2) = r.assignment["B1"], r.assignment["B2"]
    assert (d1, p1) == (d2, p2) and r1 != r2


def test_accessibility_and_capacity_and_type():
    ss = [session("A", acc=True, size=45)]
    r = solve(make(ss))
    assert r.assignment["A"][2] == "R1"                      # only accessible classroom that fits


def test_infeasible_reports_status_and_conflict_not_success():
    # one faculty, 2h/day limit, but 11 distinct one-hour sessions (max 5 days x 2h = 10h): infeasible
    ss = [session(f"S{i}", faculty="FA", groups=(("G1", "G2")[i % 2],)) for i in range(11)]
    r = solve(make(ss))
    assert r.status == "INFEASIBLE" and not r.has_solution
    assert r.diagnosis.get("conflicting_constraint_families")        # names the conflicting rules


def test_no_candidate_session_is_explained():
    r = solve(make([session("TOOBIG", size=500)]))
    assert r.status == "NO_CANDIDATES"
    assert r.diagnosis["sessions_without_candidates"]["TOOBIG"]["capacity"] >= 1


def test_deterministic_for_same_seed():
    ss = [session(f"S{i}", faculty="FB", groups=(("G1", "G2")[i % 2],)) for i in range(6)]
    a = solve(make(ss), seed=7).assignment
    b = solve(make(ss), seed=7).assignment
    assert a == b


def test_candidates_on_real_dataset_respect_per_session_rules(ds):
    c, _ = build_candidates(ds)
    for sid, cl in c.items():
        s = ds.sessions[sid]
        for (d, p, r) in cl:
            rm = ds.rooms[r]
            assert rm["capacity"] >= s["size"] and rm["type"] in s["room_types"]
            assert (not s["needs_accessible"]) or rm["accessible"]
            assert not any((d, q) in ds.fac_unavail[s["faculty_id"]] for q in range(p, p + s["duration"]))
