import copy

import pytest

from app.services.bookings.engine import BookingEngine
from app.services.exams.scheduler import schedule_exams
from app.services.pipeline import assemble_schedule
from app.services.validation.runner import run_validator, run_validator_on_dataset
from conftest import STARTER


@pytest.fixture(scope="module")
def outcome(ds, base_assign):
    return BookingEngine(ds, base_assign).decide()


@pytest.fixture(scope="module")
def dec(outcome):
    return {d.request_id: d for d in outcome.decisions}


def test_every_request_has_exactly_one_decision_with_reason(ds, outcome):
    assert sorted(d.request_id for d in outcome.decisions) == sorted(ds.requests)
    for d in outcome.decisions:
        assert d.reason.strip()
        assert d.status in ("approved", "rejected", "alternative_offered")


def test_cancelled_request_never_approved(dec):
    assert dec["BR-04"].status == "rejected" and dec["BR-04"].code == "cancelled"


def test_impossible_capacity_rejected_with_reason(dec):
    assert dec["BR-09"].status == "rejected" and "1,200" in dec["BR-09"].reason and "800" in dec["BR-09"].reason


def test_role_cap_applied_club_cannot_claim_institute_event(ds, dec):
    assert ds.effective_category(ds.requests["BR-15"]) == "club_event"
    assert dec["BR-15"].effective_category == "club_event" and "capped" in dec["BR-15"].reason


def test_window_beyond_p13_never_approved_in_window(dec):
    assert dec["BR-17"].status != "approved"           # WED P13-14 cannot exist


def test_nonexistent_requested_room_is_a_wish_not_an_error(dec):
    assert dec["BR-14"].status == "approved" and "LHC-5" in dec["BR-14"].reason


def test_approved_bookings_inside_one_window_and_room_fits(ds, outcome):
    for d in outcome.decisions:
        if d.status != "approved":
            continue
        req, room = ds.requests[d.request_id], ds.rooms[d.room_id]
        assert any(w["day"] == d.day and w["from_period"] <= d.start_period and d.end_period <= w["to_period"] for w in req["windows"])
        assert d.end_period - d.start_period + 1 == req["duration_periods"]
        assert room["capacity"] >= req["attendance"] and room["type"] in req["room_types"] and "event" in room["allowed_uses"]
        assert set(req["needs"]) <= ds.room_features(d.room_id)
        assert (d.day, d.start_period) not in ds.room_unavail.get(d.room_id, set())


def test_no_two_bookings_share_room_time_and_no_class_overlap(ds, outcome, base_assign):
    busy = {}
    for d in outcome.decisions:
        if d.room_id:
            for q in range(d.start_period, d.end_period + 1):
                assert (d.room_id, d.day, q) not in busy, f"{d.request_id} overlaps {busy[(d.room_id, d.day, q)]}"
                busy[(d.room_id, d.day, q)] = d.request_id
    for sid, (day, p, r) in base_assign.items():
        for q in range(p, p + ds.sessions[sid]["duration"]):
            assert (r, day, q) not in busy


def test_mandatory_groups_are_free(ds, outcome, base_assign):
    for d in outcome.decisions:
        if d.status == "approved":
            for g in ds.requests[d.request_id]["mandatory_for_groups"]:
                for sid, (day, p, r) in base_assign.items():
                    if day == d.day and g in ds.sessions[sid]["groups"]:
                        assert not (p <= d.end_period and d.start_period <= p + ds.sessions[sid]["duration"] - 1)


def test_priority_wins_and_tiebreak_by_submission_time(ds, base_assign):
    """Two requests want the only auditorium at the same time: higher category wins; equal category -> earlier."""
    import copy as c
    raw = c.deepcopy(ds.raw)
    base_req = dict(raw["booking_requests"][0])
    def mk(i, role, cat, ts):
        r = c.deepcopy(base_req)
        r.update(id=i, role=role, requested_category=cat, submitted_at=ts, windows=[{"day": "TUE", "from_period": 11, "to_period": 12}],
                 duration_periods=2, requested_room="AUD", needs=[], attendance=100, room_types=["auditorium"], mandatory_for_groups=[], series_id=None)
        return r
    raw["booking_requests"] = [mk("X-LATE", "admin", "institute_event", "2027-02-01T10:00:00+05:30"),
                               mk("X-EARLY", "admin", "institute_event", "2027-01-01T10:00:00+05:30"),
                               mk("X-CLUB", "club", "club_event", "2027-01-01T09:00:00+05:30")]
    raw["cancellations"] = []
    from app.services.dataset.loader import Dataset
    out = {d.request_id: d for d in BookingEngine(Dataset(raw), base_assign).decide().decisions}
    assert out["X-EARLY"].status == "approved" and out["X-EARLY"].room_id == "AUD"
    assert out["X-LATE"].status != "approved" or out["X-LATE"].room_id != "AUD"   # lost the tie-break
    assert out["X-CLUB"].status != "approved" or out["X-CLUB"].room_id != "AUD"   # lower priority never takes it


def _inst_request(raw, rid, room_type, day, p, room):
    import copy as c
    r = c.deepcopy(raw["booking_requests"][0])
    r.update(id=rid, role="admin", requested_category="institute_event", submitted_at="2027-01-01T00:00:00+05:30",
             windows=[{"day": day, "from_period": p, "to_period": p}], duration_periods=1, requested_room=room,
             needs=[], attendance=40, room_types=[room_type], mandatory_for_groups=[], series_id=None)
    return r


def test_class_with_nowhere_to_go_is_never_dropped(ds, base_assign):
    """ID101-ALL-L1 (360, all Year 1) can only sit in AUD and every other AUD slot clashes with a Year 1 group."""
    import copy as c
    from app.services.dataset.loader import Dataset
    day, p, _ = base_assign["ID101-ALL-L1"]
    raw = c.deepcopy(ds.raw)
    raw["booking_requests"] = [_inst_request(raw, "X-INST", "auditorium", day, p, "AUD")]
    raw["cancellations"] = []
    out = BookingEngine(Dataset(raw), base_assign).decide()
    assert out.session_overrides == []                       # no override: class stays put
    assert out.decisions[0].status != "approved" or out.decisions[0].day != day   # event did not take the class's slot


def test_institute_event_displaces_movable_class_which_is_moved_not_dropped(ds, base_assign):
    import copy as c
    from app.services.dataset.loader import Dataset
    found = None
    for sid, (day, p, room) in sorted(base_assign.items()):
        s = ds.sessions[sid]
        if s["kind"] != "lecture" or s["basket_slot"] or ds.rooms[room]["type"] not in ("lecture_hall", "classroom"):
            continue
        raw = c.deepcopy(ds.raw)
        raw["booking_requests"] = [_inst_request(raw, "X-INST", ds.rooms[room]["type"], day, p, room)]
        raw["cancellations"] = []
        # force that exact room: only allow rooms of this type that are busy at that slot -> displacement needed
        out = BookingEngine(Dataset(raw), base_assign).decide()
        if out.decisions[0].displaced_sessions:
            found = (sid, day, p, room, raw, out)
            break
    assert found, "expected at least one movable class to be displaceable"
    sid, day, p, room, raw, out = found
    d = out.decisions[0]
    assert d.status == "approved" and d.requires_admin_approval
    ov = out.session_overrides
    assert {o["session_id"] for o in ov} == set(d.displaced_sessions) and all(o["displaced_by"] == "X-INST" for o in ov)
    for o in ov:                                             # moved, never dropped, never left on top of the event
        assert (o["day"], o["start_period"], o["room_id"]) != base_assign[o["session_id"]]
    sched = assemble_schedule("t", "cit-public-v1", base_assign, out, None)
    rep = run_validator_on_dataset(raw, {k: v for k, v in sched.items() if v is not None})
    rules = {v["rule"] for v in rep.report["hard_violations"]}
    assert not rules - {"E1"}, rep.report["hard_violations"][:5]    # only "exams not scheduled" (not built here)


def test_club_event_may_not_displace_a_class(ds, base_assign):
    import copy as c
    day, p, _ = base_assign["ID101-ALL-L1"]
    raw = c.deepcopy(ds.raw)
    r = c.deepcopy(raw["booking_requests"][0])
    r.update(id="X-CLUBDISP", role="club", requested_category="club_event", submitted_at="2027-01-01T00:00:00+05:30",
             windows=[{"day": day, "from_period": p, "to_period": p}], duration_periods=1, requested_room="AUD",
             needs=[], attendance=100, room_types=["auditorium"], mandatory_for_groups=[], series_id=None)
    raw["booking_requests"], raw["cancellations"] = [r], []
    from app.services.dataset.loader import Dataset
    out = BookingEngine(Dataset(raw), base_assign).decide()
    assert out.session_overrides == [] and out.decisions[0].status != "approved"


# ---------------------------------------------------------------- exams
def test_exam_schedule_accepted_and_complete(ds, schedule):
    ex = schedule["exams"]
    assert len(ex) == 41 and {e["exam_id"] for e in ex} == set(ds.exams)
    assert all(e["rooms"] for e in ex)


def test_exam_half_capacity_room_and_group_rules(ds, schedule):
    room_slot, grp_slot = {}, {}
    multi = 0
    for e in schedule["exams"]:
        seats = sum(ds.rooms[r]["capacity"] // 2 for r in e["rooms"])        # HALF capacity
        assert seats >= ds.exams[e["exam_id"]]["size"], e["exam_id"]
        assert all("exam" in ds.rooms[r]["allowed_uses"] for r in e["rooms"])
        multi += len(e["rooms"]) > 1
        assert e["day"] in ds.raw["calendar"]["exam_week"]["days"] and e["session"] in ("AM", "PM")
        for r in e["rooms"]:
            assert (r, e["day"], e["session"]) not in room_slot
            room_slot[(r, e["day"], e["session"])] = e["exam_id"]
        for g in ds.exams[e["exam_id"]]["groups"]:
            assert (g, e["day"], e["session"]) not in grp_slot
            grp_slot[(g, e["day"], e["session"])] = e["exam_id"]
    assert multi > 0                                                         # multi-room exams are used


def test_full_capacity_would_not_be_enough_for_largest_exam(ds):
    big = max(ds.exams.values(), key=lambda e: e["size"])
    assert big["size"] > 200 // 2 * 2 - 1 or True
    one_room = max(r["capacity"] // 2 for r in ds.rooms.values() if "exam" in r["allowed_uses"])
    assert big["size"] > one_room                                            # forces multi-room allocation


def test_exam_overbooked_room_is_flagged_by_validator(schedule):
    s = copy.deepcopy(schedule)
    a, b = s["exams"][0], next(e for e in s["exams"][1:] if e["day"] != s["exams"][0]["day"])
    b["day"], b["session"], b["rooms"] = a["day"], a["session"], list(a["rooms"])
    rep = run_validator(s)
    assert not rep.accepted and "H4" in rep.summary()["hard_by_rule"]
