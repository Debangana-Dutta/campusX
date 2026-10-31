"""Part 2 backend: student scope, notifications from real events, approval workflow, parser, Campus Buddy, AI fallback."""
import datetime as dt
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai import booking_parser, buddy, gemini
from app.state import STATE
from conftest import ROOT


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        tok = c.post("/api/auth/local-login", json={"username": "admin", "password": "campusx-demo"}).json()["token"]
        assert c.post("/api/admin/demo-reset", headers={"Authorization": f"Bearer {tok}"}).json()["reset"]   # clean state
        yield c


def H(c, u):
    return {"Authorization": "Bearer " + c.post("/api/auth/local-login", json={"username": u, "password": "campusx-demo"}).json()["token"]}


def test_app_boots_populated_and_official_validator_accepted(client):
    s = client.get("/api/admin/summary", headers=H(client, "admin")).json()
    assert s["sessions_scheduled"] == 189 and s["validation"]["accepted"] and s["validation"]["hard_violation_count"] == 0
    assert s["timetable_status"] in ("approved", "validated")


def test_student_is_read_only_and_scoped(client):
    st = H(client, "student")
    assert client.get("/api/timetable", headers=st).status_code == 403
    assert client.get("/api/timetable/group/CSE-2", headers=st).status_code == 200
    assert client.get("/api/timetable/group/ME-3", headers=st).status_code == 403
    assert client.get("/api/bookings", headers=st).status_code == 403
    assert client.post("/api/timetable/generate", json={}, headers=st).status_code == 403
    assert client.get("/api/admin/summary", headers=st).status_code == 403
    ex = client.get("/api/exams", headers=st).json()["exams"]
    assert ex and all("CSE-2" in e["groups"] for e in ex)


def test_invalid_schedule_cannot_be_approved(client):
    old = dict(STATE.assignment)
    a, b = list(old)[:2]
    STATE.assignment[b] = old[a]
    STATE.validate()
    try:
        assert STATE.status() == "invalid"
        r = client.post("/api/timetable/approve", headers=H(client, "admin"))
        assert r.status_code == 409
    finally:
        STATE.assignment = old
        STATE.validate()
        STATE.approve("system (validated export)")


def test_notifications_come_from_real_events_and_read_state(client):
    club = H(client, "club")
    before = client.get("/api/notifications", headers=club).json()["unread"]
    body = {"title": "Quiz night", "attendance": 30, "duration_periods": 2, "room_types": ["classroom"],
            "windows": [{"day": "MON", "from_period": 12, "to_period": 13}], "needs": []}
    r = client.post("/api/bookings", json=body, headers=club)
    assert r.status_code == 201
    n = client.get("/api/notifications", headers=club).json()
    assert n["unread"] == before + 1 and "approved" in n["items"][0]["message"] and n["items"][0]["link"]
    assert client.post("/api/notifications/read", json={"ids": [n["items"][0]["id"]]}, headers=club).json()["marked"] == 1
    assert client.get("/api/notifications", headers=club).json()["unread"] == before
    # another user never sees the club's private notification
    assert all("Quiz night" not in i["message"] for i in client.get("/api/notifications", headers=H(client, "faculty")).json()["items"])


def test_announcement_broadcast_and_permissions(client):
    assert client.post("/api/notifications/announce", json={"message": "Hello all"}, headers=H(client, "club")).status_code == 403
    assert client.post("/api/notifications/announce", json={"message": "Library closed Friday"}, headers=H(client, "admin")).status_code == 200
    for u in ("student", "faculty"):
        assert any("Library closed" in i["message"] for i in client.get("/api/notifications", headers=H(client, u)).json()["items"])


def test_alternative_can_be_accepted_or_declined_by_requester(client):
    club = H(client, "club")
    # ask for an auditorium slot that is already booked (BR-01 holds AUD MON P4-5) -> engine must not overwrite it
    body = {"title": "Dance show", "attendance": 100, "duration_periods": 2, "room_types": ["auditorium"],
            "windows": [{"day": "MON", "from_period": 4, "to_period": 5}], "needs": []}
    r = client.post("/api/bookings", json=body, headers=club).json()
    assert r["decision"]["status"] == "alternative_offered" and r["state"] == "proposed"
    assert (r["decision"]["day"], r["decision"]["start_period"]) != ("MON", 4)
    ok = client.post(f"/api/bookings/{r['id']}/respond", json={"accept": True}, headers=club).json()
    assert ok["state"] == "confirmed"
    # a different user cannot respond
    assert client.post(f"/api/bookings/{r['id']}/respond", json={"accept": True}, headers=H(client, "faculty")).status_code == 404


def test_role_assignment_cannot_self_assign(client):
    assert client.post("/api/admin/role-assignments", json={"user_id": "admin", "role": "admin"}, headers=H(client, "admin")).status_code == 403
    assert client.post("/api/admin/role-assignments", json={"user_id": "x1", "role": "wizard"}, headers=H(client, "admin")).status_code == 422
    assert client.post("/api/admin/role-assignments", json={"user_id": "x1", "role": "faculty"}, headers=H(client, "club")).status_code == 403


def test_demo_reset_admin_only_and_restores(client):
    assert client.post("/api/admin/demo-reset", headers=H(client, "club")).status_code == 403
    r = client.post("/api/admin/demo-reset", headers=H(client, "admin")).json()
    assert r["reset"] and r["timetable_loaded_from_export"] and r["status"] == "approved"
    assert client.get("/api/bookings", headers=H(client, "club")).json()["count"] == 0


# ------------------------------------------------------------------ parser
def test_parser_matches_readme_examples():
    mon = dt.date(2026, 10, 26)
    r = booking_parser.parse_rules("Need a room for 45 people on Tuesday 6 to 8 pm, projector please.", mon)["fields"]
    assert r["attendance"] == 45 and r["duration_periods"] == 2 and r["needs"] == ["projector"]
    assert r["windows"] == [{"day": "TUE", "from_period": 10, "to_period": 11}]
    assert r["room_types"] == ["classroom", "lecture_hall", "seminar_hall"]
    h = booking_parser.parse_rules("seminar hall kal shaam 6 baje, 2 ghante, 100 log, mic chahiye", mon)["fields"]
    assert h["windows"] == [{"day": "TUE", "from_period": 10, "to_period": 11}]       # Monday + kal = Tuesday
    assert h["room_types"] == ["seminar_hall"] and h["needs"] == ["pa_system"] and h["attendance"] == 100


def test_parser_asks_instead_of_inventing():
    r = booking_parser.parse_rules("Need somewhere for the quiz finals after lunch on Thursday, maybe 150 people.", dt.date(2026, 10, 26))
    assert any("long" in q for q in r["follow_up"])            # duration not stated -> follow-up
    assert r["assumptions"]                                       # 'after lunch' assumption is made visible
    assert booking_parser.parse_rules("book something", dt.date(2026, 10, 26))["follow_up"]


def test_parser_endpoint_flags_named_room_conflict(client):
    r = client.post("/api/bookings/parse", headers=H(client, "club"),
                    json={"text": "I want SH-2 on Friday at 10 am for a wheelchair-accessible poster session, 60 people for 2 hours"}).json()
    assert r["fields"]["requested_room"] == "SH-2" and any("SH-2 lacks" in w and "SH-1" in w for w in r["warnings"])
    assert r["ai_used"] is False and r["ai_error"]


def test_gemini_output_is_validated_and_bad_output_discarded(monkeypatch):
    monkeypatch.setattr(gemini, "configured", lambda: True)
    good = {"attendance": 50, "duration_periods": 2, "windows": [{"day": "WED", "from_period": 10, "to_period": 11}],
            "room_types": ["seminar_hall"], "needs": ["projector", "jacuzzi"], "title": "Talk", "follow_up": []}
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: json.dumps(good))
    r = booking_parser.parse("seminar hall wednesday 6-8pm 50 people", dt.date(2026, 10, 26))
    assert r["ai_used"] and r["fields"]["needs"] == ["projector"]            # unknown feature dropped
    bad = {**good, "windows": [{"day": "SUN", "from_period": 1, "to_period": 2}]}
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: json.dumps(bad))
    r = booking_parser.parse("seminar hall wednesday 6-8pm 50 people", dt.date(2026, 10, 26))
    assert not r["ai_used"] and "invalid" in r["ai_error"]                    # invalid structure rejected safely
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: (_ for _ in ()).throw(gemini.GeminiUnavailable("quota")))
    r = booking_parser.parse("seminar hall wednesday 6-8pm 50 people", dt.date(2026, 10, 26))
    assert not r["ai_used"] and r["fields"]["attendance"] == 50               # fallback still works


def test_ai_never_decides_booking_status(client):
    """Even if the parser claimed approval, the engine decides: a 1,200-seat request is rejected."""
    club = H(client, "club")
    r = client.post("/api/bookings", headers=club, json={"title": "Huge fest", "attendance": 1200, "duration_periods": 3,
                    "room_types": ["auditorium", "outdoor"], "windows": [{"day": "FRI", "from_period": 10, "to_period": 12}]}).json()
    assert r["state"] == "rejected"


# ------------------------------------------------------------------ buddy
def _ask(client, who, q):
    return client.post("/api/buddy/ask", headers=H(client, who), json={"question": q}).json()


def test_buddy_answers_from_backend_data_english_and_hinglish(client):
    a = _ask(client, "student", "Where is my next lecture?")
    assert a["intent"] == "next" and " in " in a["answer"] and not a["ai_used"]
    h = _ask(client, "student", "Aaj meri next class kaha hai?")
    assert h["intent"] == "next"
    e = _ask(client, "student", "Kal mera exam kab hai?")
    assert e["intent"] == "exam" and e["facts"]["exams"]
    t = _ask(client, "student", "Who is teaching CS201?")
    assert "Dr. Rohit Sahoo" in t["answer"]


def test_buddy_day_queries_use_real_timetable(client):
    ds = STATE.ds
    mon = [s for s, e in STATE.assignment.items() if e[0] == "MON" and "CSE-2" in ds.sessions[s]["groups"]]
    now = dt.datetime(2026, 10, 26, 7, 0, tzinfo=buddy.IST)       # a Monday morning
    out = buddy.ask("what are my classes today", __import__("app.core.auth", fromlist=["User"]).User("student", "student", "s", group_id="CSE-2"),
                    ds, STATE.assignment, STATE.exams, [], now=now)
    assert {c["session"] for c in out["facts"]["classes"]} == set(mon)
    free = buddy.ask("do I have a free period today", __import__("app.core.auth", fromlist=["User"]).User("student", "student", "s", group_id="CSE-2"),
                     ds, STATE.assignment, STATE.exams, [], now=now)
    assert len(free["facts"]["free_periods"]) == 9 - sum(ds.sessions[s]["duration"] for s in mon)


def test_buddy_does_not_leak_other_groups(client):
    # a student passing someone else's group is ignored; only own group data is used
    r = client.post("/api/buddy/ask", headers=H(client, "student"), json={"question": "my classes monday", "group_id": "ME-3"}).json()
    assert r["facts"]["scope"] == "group CSE-2"
    club = _ask(client, "club", "what are my classes today")
    assert club["facts"]["scope"] == "none" and "own profile" in club["answer"]


def test_buddy_gemini_only_rephrases_and_failure_falls_back(client, monkeypatch):
    monkeypatch.setattr(gemini, "configured", lambda: True)
    seen = {}
    def fake(system, prompt, **k):
        seen["prompt"] = prompt
        return "Rephrased answer"
    monkeypatch.setattr(gemini, "generate", fake)
    r = _ask(client, "student", "when is my next exam")
    assert r["ai_used"] and r["answer"] == "Rephrased answer"
    assert "ME-3" not in seen["prompt"] and "FACTS" in seen["prompt"]          # only permitted facts are sent
    monkeypatch.setattr(gemini, "generate", lambda *a, **k: (_ for _ in ()).throw(gemini.GeminiUnavailable("down")))
    r = _ask(client, "student", "when is my next exam")
    assert not r["ai_used"] and r["ai_error"] and "Your next exam" in r["answer"]
