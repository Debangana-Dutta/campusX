import copy
import json

import pytest

from app.services.dataset.loader import Dataset, apply_disruption
from app.services.disruptions.repair import repair_timetable
from app.services.pipeline import apply_change_and_export
from app.services.scheduling.solver import from_schedule
from app.services.validation.runner import run_validator
from conftest import STARTER

pytestmark = pytest.mark.slow


def test_sample_disruption_export_accepted_by_official_cli(schedule, schedule_after):
    r = run_validator(schedule_after, disruption_path=STARTER / "examples" / "sample_disruption.json", baseline=schedule)
    assert r.accepted, r.summary()["hard_violations"][:5]
    assert r.summary()["stability"]["sessions_moved"] <= 15


def test_repair_preserves_baseline_and_moves_only_what_must_move(raw, disruption, base_assign):
    rep = repair_timetable(raw, disruption, base_assign, time_limit_s=60)
    assert rep.ok and rep.status in ("OPTIMAL", "FEASIBLE")
    moved = {m["session_id"] for m in rep.moved}
    assert moved == set(rep.affected)                       # nothing unaffected was disturbed
    assert len(moved) + len(rep.unchanged) == 189           # every baseline session accounted for
    assert [a["session_id"] for a in rep.added] == ["CS202-T2"]
    assert "Proven minimum" in rep.minimality
    for sid in rep.unchanged:
        assert rep.assignment[sid] == base_assign[sid]
    # baseline untouched
    assert base_assign["ID101-ALL-L1"][2] == "AUD"


def test_remove_session_and_add_faculty_and_new_session(raw, base_assign):
    sess = copy.deepcopy(raw["sessions"][0])
    new_fac = {"id": "F99", "name": "New Prof", "department": "CSE", "max_hours_per_day": 4, "needs_accessible": False,
               "unavailable": [], "preferences": []}
    new_sess = {**sess, "id": "NEW-1", "faculty_id": "F99", "kind": "tutorial", "size": 30, "duration": 1,
                "groups": ["CSE-2"], "basket_slot": None, "fixed_slot": None, "room_types": ["classroom"]}
    dis = {"changes": [{"type": "remove_session", "session_id": "HS201-H2-L2"},
                       {"type": "add_faculty", "faculty": new_fac},
                       {"type": "add_session", "session": new_sess}]}
    rep = repair_timetable(raw, dis, base_assign, time_limit_s=40)
    assert rep.ok
    assert rep.removed == ["HS201-H2-L2"] and "HS201-H2-L2" not in rep.assignment
    assert "NEW-1" in rep.assignment and rep.moved == []     # nothing had to move
    assert rep.assignment["NEW-1"] is not None


def test_repaired_schedule_passes_official_validator_for_new_change_types(raw, base_assign, schedule):
    dis = {"changes": [{"type": "remove_session", "session_id": "HS201-H2-L2"}]}
    res = apply_change_and_export(raw, dis, schedule, team="t", seed=42, time_limit_s=40)
    after = res["schedule_after"]
    tmp = STARTER.parent.parent.parent / "backend" / "var" / "_t_dis.json"
    tmp.write_text(json.dumps(dis))
    try:
        r = run_validator(after, disruption_path=tmp, baseline=schedule)
    finally:
        tmp.unlink()
    assert r.accepted and r.summary()["stability"]["sessions_moved"] == 0


def test_infeasible_change_reports_conflict_instead_of_faking_success(raw, base_assign):
    # no room anywhere can seat a 400-person lecture that needs a lab type -> impossible session
    impossible = {**copy.deepcopy(raw["sessions"][0]), "id": "IMPOSSIBLE", "size": 900, "room_types": ["lecture_hall"],
                  "basket_slot": None, "fixed_slot": None}
    rep = repair_timetable(raw, {"changes": [{"type": "add_session", "session": impossible}]}, base_assign, time_limit_s=20)
    assert not rep.ok and rep.status == "NO_CANDIDATES"
    assert rep.conflict["sessions"]["IMPOSSIBLE"]["capacity"] >= 1


def test_whole_week_leave_for_overloaded_faculty_is_reported(raw, base_assign):
    dis = {"changes": [{"type": "faculty_unavailable", "faculty_id": "F03", "days": ["MON", "TUE", "WED", "THU", "FRI"],
                        "periods": list(range(1, 10)), "reason": "leave"}]}
    rep = repair_timetable(raw, dis, base_assign, time_limit_s=30)
    assert not rep.ok                                         # F03 has 9 hours/week: nothing can be placed
    assert rep.conflict and rep.status in ("NO_CANDIDATES", "INFEASIBLE")


def test_unknown_change_type_rejected(raw, base_assign):
    rep = repair_timetable(raw, {"changes": [{"type": "meteor"}]}, base_assign, time_limit_s=10)
    assert rep.status == "INVALID_DISRUPTION" and not rep.ok
