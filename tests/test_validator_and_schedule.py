"""Official validator integration + independent re-check of every hard constraint on the app's own export."""
import copy
from collections import defaultdict

import pytest

from app.services.scheduling.scoring import soft_penalties
from app.services.scheduling.solver import from_schedule
from app.services.validation.runner import run_validator
from conftest import STARTER


def test_exit_code_zero_is_not_acceptance():
    import json
    ex = json.loads((STARTER / "examples" / "schedule.example.json").read_text())
    r = run_validator(ex)
    assert r.ran and r.exit_code == 0
    assert not r.accepted and r.hard_violation_count > 0     # example is explicitly NOT a valid solution


def test_app_export_accepted_by_official_validator(schedule):
    r = run_validator(schedule)
    assert r.accepted, r.summary()["hard_violations"][:5]
    assert r.hard_violation_count == 0
    s = r.summary()
    assert s["priority_inversions"] == []
    assert s["booking"]["booking_score"] >= 60


@pytest.mark.parametrize("mutate,rule", [
    ("drop_session", "H1"),
    ("double_room", "H4"),
    ("bad_room_type", "H6"),
    ("lab_wrong_start", "H9"),
])
def test_validator_catches_mutations(schedule, ds, mutate, rule):
    s = copy.deepcopy(schedule)
    es = s["sessions"]
    if mutate == "drop_session":
        es.pop(0)
    elif mutate == "double_room":
        a, b = es[0], next(e for e in es[1:] if e["room_id"] != es[0]["room_id"])
        b["day"], b["start_period"], b["room_id"] = a["day"], a["start_period"], a["room_id"]
    elif mutate == "bad_room_type":
        e = next(e for e in es if ds.sessions[e["session_id"]]["kind"] == "lecture")
        e["room_id"] = "CS-LAB-1"
    elif mutate == "lab_wrong_start":
        e = next(e for e in es if ds.sessions[e["session_id"]]["kind"] == "lab")
        e["start_period"] = 3
    r = run_validator(s)
    assert not r.accepted
    assert rule in r.summary()["hard_by_rule"]


def test_local_soft_mirror_equals_official(ds, schedule):
    r = run_validator(schedule)
    assert soft_penalties(ds, from_schedule(schedule)) == r.report["soft_penalties"]


# ---- independent hard-constraint re-check (does not call the validator)
@pytest.fixture(scope="module")
def occ(ds, schedule):
    a = from_schedule(schedule)
    return a


def test_every_session_exactly_once(ds, schedule):
    ids = [e["session_id"] for e in schedule["sessions"]]
    assert sorted(ids) == sorted(ds.sessions) and len(ids) == len(set(ids)) == 189


def test_no_overlaps_and_per_session_rules(ds, occ):
    room, fac, grp = defaultdict(list), defaultdict(list), defaultdict(set)
    fac_day = defaultdict(int)
    basket = defaultdict(set)
    for sid, (d, p, r) in occ.items():
        s, rm = ds.sessions[sid], ds.rooms[r]
        per = range(p, p + s["duration"])
        assert 1 <= p and per[-1] <= 9, sid                                  # inside P1-P9
        assert not (p <= 5 < per[-1]), f"{sid} crosses lunch"
        if s["kind"] == "lab":
            assert p in (2, 6), sid                                          # lab start periods
        assert rm["capacity"] >= s["size"], sid                              # H5
        assert rm["type"] in s["room_types"], sid                            # H6
        if s["needs_accessible"]:
            assert rm["accessible"], sid                                     # H10
        assert not any((d, q) in ds.fac_unavail[s["faculty_id"]] for q in per), sid   # H7
        assert not any((d, q) in ds.room_unavail.get(r, ()) for q in per), sid        # H8
        if s["fixed_slot"]:
            assert (d, p) == (s["fixed_slot"]["day"], s["fixed_slot"]["start_period"])  # H14
        for q in per:
            room[(r, d, q)].append(sid)
            fac[(s["faculty_id"], d, q)].append(sid)
            for g in s["groups"]:
                grp[(g, d, q)].add(s["basket_slot"] or sid)
        fac_day[(s["faculty_id"], d)] += s["duration"]
        if s["basket_slot"]:
            basket[s["basket_slot"]].add((d, p))
    assert all(len(v) == 1 for v in room.values())          # H4
    assert all(len(v) == 1 for v in fac.values())           # H2
    assert all(len(v) == 1 for v in grp.values())           # H3 (basket members count once)
    assert all(len(v) == 1 for v in basket.values())        # H11 elective synchronisation
    assert all(h <= ds.faculty[f]["max_hours_per_day"] for (f, _), h in fac_day.items())   # H12
    assert len(basket) == 3                                 # OEB-1..3 all present
