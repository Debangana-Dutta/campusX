"""Priority order, manual scheduling, explanations, faculty assistant, Admin data management, repair evidence."""
import copy

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.audit import notify
from app.services.disruptions.repair import repair_timetable
from app.services.scheduling.solver import from_schedule
from app.state import STATE, AppState
from conftest import ROOT

PW = "campusx-demo"


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        h = H(c, "admin")
        assert c.post("/api/admin/demo-reset", headers=h).json()["reset"]
        yield c


def H(c, who):
    return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": f"{who}@opticampus.demo", "password": PW}).json()["token"]}


# ------------------------------------------------------------------ priority order
def test_priority_order_admin_only_and_validated(client):
    a = H(client, "admin")
    cur = client.get("/api/admin/priority-order", headers=a).json()["order"]
    assert cur[:2] == ["exam", "regular_session"]
    assert client.put("/api/admin/priority-order", json={"order": cur}, headers=H(client, "club")).status_code == 403
    assert client.put("/api/admin/priority-order", json={"order": cur[:-1]}, headers=a).status_code == 422
    assert client.put("/api/admin/priority-order", json={"order": ["regular_session", "exam", *cur[2:]]}, headers=a).status_code == 422
    new = ["exam", "regular_session", "guest_lecture", "institute_event", "department_event", "club_event"]
    assert client.put("/api/admin/priority-order", json={"order": new}, headers=a).status_code == 200
    assert client.get("/api/admin/priority-order", headers=a).json()["order"] == new
    assert STATE.ds.raw["priority_order"] == new
    assert STATE.last_validation["accepted"]                       # bookings re-decided and the official validator still accepts
    # persists across a restart, and demo reset restores the default
    fresh = AppState(); fresh.import_dataset()
    assert fresh.live_raw["priority_order"] == new
    assert client.post("/api/admin/demo-reset", headers=a).json()["reset"]
    assert client.get("/api/admin/priority-order", headers=a).json()["order"] == cur


# ------------------------------------------------------------------ manual scheduling uses the same validation
MAN = {"title": "Dept seminar", "attendance": 40, "duration_periods": 2, "room_id": "SH-1", "day": "TUE", "start_period": 10,
       "requested_category": "department_event", "department": "CSE"}


def test_manual_scheduling_validates_like_automatic(client):
    co, fa, cl = H(client, "coordinator"), H(client, "faculty"), H(client, "club")
    assert client.post("/api/bookings/manual", json=MAN, headers=cl).status_code == 403                  # club cannot schedule manually
    r = client.post("/api/bookings/manual", json=MAN, headers=co)
    assert r.status_code == 201 and r.json()["state"] == "confirmed"
    # same room/time again -> blocked, with reasons (confirmed bookings are never overwritten)
    dup = client.post("/api/bookings/manual", json={**MAN, "title": "Clash"}, headers=co)
    assert dup.status_code == 409 and any("already used" in e for e in dup.json()["error"]["detail"]["errors"])
    # capacity, type/needs, closure, bad duration/room
    assert client.post("/api/bookings/manual", json={**MAN, "title": "Too big", "attendance": 500, "start_period": 12}, headers=co).status_code == 409
    assert client.post("/api/bookings/manual", json={**MAN, "title": "Needs", "room_id": "SH-2", "needs": ["accessible"], "start_period": 12}, headers=co).status_code == 409
    assert client.post("/api/bookings/manual", json={**MAN, "title": "Unknown room", "room_id": "NOPE"}, headers=co).status_code == 422
    # a class in the way (LH-4 is closed Thursday: maintenance window)
    closed = client.post("/api/bookings/manual", json={**MAN, "title": "Closed", "room_id": "LH-4", "day": "THU", "start_period": 3, "attendance": 30}, headers=co)
    assert closed.status_code == 409
    # coordinators schedule only for their department; faculty requests need approval
    assert client.post("/api/bookings/manual", json={**MAN, "title": "Other dept", "department": "ME", "start_period": 12, "room_id": "SH-2"}, headers=co).status_code == 403
    f = client.post("/api/bookings/manual", json={**MAN, "title": "Faculty ask", "start_period": 12, "room_id": "SH-2"}, headers=fa)
    assert f.status_code == 201 and f.json()["state"] == "proposed"


def test_manual_booking_respects_mandatory_group_classes(client):
    co = H(client, "coordinator")
    tt = client.get("/api/timetable", headers=co).json()["sessions"]
    e = next(x for x in tt if "CSE-3" in x["groups"] and x["end_period"] == x["start_period"])
    r = client.post("/api/bookings/manual", json={**MAN, "title": "Group clash", "day": e["day"], "start_period": e["start_period"],
                                                 "duration_periods": 1, "room_id": "SH-1", "mandatory_for_groups": ["CSE-3"]}, headers=co)
    assert r.status_code == 409 and any("mandatory" in x for x in r.json()["error"]["detail"]["errors"])


# ------------------------------------------------------------------ explanations from real data
def test_explain_session_uses_real_facts(client):
    st = H(client, "student")
    sid = next(x["session_id"] for x in client.get("/api/timetable/group/CSE-2", headers=st).json()["sessions"])
    ex = client.get(f"/api/timetable/explain/{sid}", headers=st).json()
    text = " ".join(ex["facts"])
    assert sid in text and "possible day/period slots" in text and "seats" in text
    other = next(s for s, v in STATE.assignment.items() if "CSE-2" not in STATE.ds.sessions[s]["groups"])
    assert client.get(f"/api/timetable/explain/{other}", headers=st).status_code == 403


def test_buddy_explains_why(client):
    r = client.post("/api/buddy/ask", headers=H(client, "student"), json={"question": "Why is CS201 scheduled where it is?"}).json()
    assert r["intent"] == "why" and r["facts"].get("explanation") and "CS201" in r["answer"]


# ------------------------------------------------------------------ faculty assistant drafts only
def test_faculty_assistant_drafts_and_asks_followups(client):
    fa = H(client, "faculty")
    d = client.post("/api/assistant/schedule-request", json={"text": "I can't teach on Monday and Tuesday morning, conference"}, headers=fa).json()
    assert d["draft"]["days"] == ["MON", "TUE"] and d["draft"]["periods"] == [1, 2, 3, 4, 5] and d["draft"]["faculty_id"] == "F01"
    assert client.post("/api/assistant/schedule-request", json={"text": "I am unavailable sometime soon"}, headers=fa).json()["follow_up"]
    assert client.post("/api/assistant/schedule-request", json={"text": "unavailable Monday"}, headers=H(client, "club")).status_code == 403
    before = dict(STATE.assignment)
    client.post("/api/assistant/schedule-request", json={"text": "unavailable Friday all day"}, headers=fa)
    assert STATE.assignment == before                                           # drafting never touches the timetable


# ------------------------------------------------------------------ Admin data management
def test_admin_data_crud_persists_and_is_integrity_checked(client):
    a = H(client, "admin")
    assert client.get("/api/admin/data/rooms", headers=H(client, "faculty")).status_code == 403
    room = {"id": "CR-999", "name": "Test Room", "building": "T", "type": "classroom", "capacity": 40, "features": ["projector"], "accessible": True, "allowed_uses": ["lecture", "tutorial", "event"]}
    assert client.post("/api/admin/data/rooms", json=room, headers=a).status_code == 201
    assert client.post("/api/admin/data/rooms", json=room, headers=a).status_code == 409
    assert any(r["id"] == "CR-999" for r in client.get("/api/admin/data/rooms", headers=a).json()["items"])
    fresh = AppState(); fresh.import_dataset()
    assert "CR-999" in fresh.live_raw["rooms"].__repr__()                       # persisted in the database
    up = client.put("/api/admin/data/rooms/CR-999", json={**room, "capacity": 55}, headers=a)
    assert up.status_code == 200 and up.json()["capacity"] == 55
    assert client.delete("/api/admin/data/rooms/CR-999", headers=a).status_code == 200
    # integrity: cannot delete a room in use, a faculty teaching sessions, or add a session with an unknown faculty
    used = next(iter(STATE.assignment.values()))[2]
    assert client.delete(f"/api/admin/data/rooms/{used}", headers=a).status_code == 409
    assert client.delete("/api/admin/data/faculty/F01", headers=a).status_code == 422
    sess = copy.deepcopy(STATE.live_raw["sessions"][0]); sess.update(id="NEW-X", faculty_id="NOPE")
    assert client.post("/api/admin/data/sessions", json=sess, headers=a).status_code == 422
    assert client.get("/api/admin/data/widgets", headers=a).status_code == 404
    assert STATE.last_validation["accepted"]
    exp = client.get("/api/admin/export/dataset", headers=a).json()
    assert len(exp["sessions"]) == 189
    assert client.post("/api/admin/demo-reset", headers=a).json()["reset"]      # reset restores the original data


def test_dataset_import_rejects_broken_files(client):
    a = H(client, "admin")
    bad = copy.deepcopy(STATE.raw); bad["sessions"][0]["faculty_id"] = "NOPE"
    r = client.post("/api/admin/import/dataset", json=bad, headers=a)
    assert r.status_code == 422 and STATE.assignment                           # nothing replaced
    assert client.post("/api/admin/import/dataset", json=STATE.raw, headers=H(client, "club")).status_code == 403


# ------------------------------------------------------------------ disruption: real optimisation evidence
@pytest.mark.slow
def test_repair_reports_solver_evidence_not_just_a_count(raw, disruption, base_assign):
    rep = repair_timetable(raw, disruption, base_assign, time_limit_s=120)
    ev = rep.evidence
    assert rep.ok and ev["full_model_status"] == "OPTIMAL" and ev["proven_minimum"]
    assert ev["objective"] == ev["best_bound"]                                  # solver closed the gap
    assert ev["moved_total"] == len(rep.moved) == ev["time_slot_changes"] + ev["room_only_changes"]
    assert ev["unchanged"] + ev["moved_total"] == 189
    assert ev["room_only_changes"] > ev["time_slot_changes"]                    # secondary objective prefers room-only moves
    assert "objective" in rep.minimality and "OPTIMAL" in rep.minimality


# ------------------------------------------------------------------ parser examples from the brief
def test_parser_handles_the_briefs_english_and_hinglish_examples():
    import datetime as dt
    from app.services.ai.booking_parser import parse_rules
    mon = dt.date(2026, 10, 26)
    a = parse_rules("Need the auditorium on Friday from 6 to 8 PM for Spectra.", mon)["fields"]
    assert a["room_types"] == ["auditorium"] and a["windows"] == [{"day": "FRI", "from_period": 10, "to_period": 11}] and a["requested_category"] == "institute_event"
    h = parse_rules("Humein seminar hall chahiye Wednesday ko 2 baje se 4 baje tak.", mon)
    assert h["fields"]["windows"] == [{"day": "WED", "from_period": 6, "to_period": 7}] and h["fields"]["duration_periods"] == 2
    assert h["fields"]["room_types"] == ["seminar_hall"] and any("people" in q for q in h["follow_up"])      # asks, does not invent attendance
    c = parse_rules("Book computer lab 2 for a coding workshop.", mon)
    assert c["fields"]["requested_room"] == "CS-LAB-2" and c["fields"]["room_types"] == ["lab_cs"]
    assert len(c["follow_up"]) >= 3                                                                           # day, time, attendance missing


# ------------------------------------------------------------------ reject proposal / department notification
@pytest.mark.slow
def test_rejected_disruption_never_changes_the_timetable_and_routes_notifications(client):
    fa, co, ad = H(client, "faculty"), H(client, "coordinator"), H(client, "admin")
    before = dict(STATE.assignment)
    p = client.post("/api/disruptions/preview", headers=fa, json={"changes": [{"type": "faculty_unavailable", "faculty_id": "F01", "days": ["TUE"], "periods": [1, 2, 3]}], "time_limit_s": 60}).json()
    assert p["feasible"] and p["status"] == "previewed"
    assert any(p["id"] in i["message"] for i in client.get("/api/notifications", headers=ad).json()["items"])     # admin notified
    assert any(p["id"] in i["message"] for i in client.get("/api/notifications", headers=co).json()["items"])     # CSE coordinator notified
    assert not any(p["id"] in i["message"] for i in client.get("/api/notifications", headers=H(client, "club")).json()["items"])
    assert client.post(f"/api/disruptions/{p['id']}/reject", json={}, headers=fa).status_code == 403            # faculty cannot decide
    assert client.post(f"/api/disruptions/apply?did={p['id']}", headers=fa).status_code == 403
    r = client.post(f"/api/disruptions/{p['id']}/reject", json={"reason": "Exam invigilation that day"}, headers=ad)
    assert r.status_code == 200
    assert STATE.assignment == before                                                                         # timetable untouched
    assert client.post(f"/api/disruptions/apply?did={p['id']}", headers=ad).status_code == 409                 # cannot apply a rejected proposal
    assert any("not approved" in i["message"] and "invigilation" in i["message"] for i in client.get("/api/notifications", headers=fa).json()["items"])


# ------------------------------------------------------------------ secure admin creation
def test_create_admin_script(tmp_path):
    import os, subprocess, sys
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path}/a.db", "STATE_DIR": str(tmp_path), "CREATE_ADMIN_PASSWORD": "Str0ngAdminPass"}
    run = lambda *args, e=env: subprocess.run([sys.executable, str(ROOT / "scripts" / "create_admin.py"), *args], capture_output=True, text=True, env=e, cwd=ROOT)
    ok = run("--email", "dean@college.edu", "--name", "Dean")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert run("--email", "dean@college.edu", "--name", "Dean").returncode == 3                               # no overwrite
    assert run("--email", "x@y.com", "--name", "X", e={**env, "CREATE_ADMIN_PASSWORD": "weak"}).returncode == 2
