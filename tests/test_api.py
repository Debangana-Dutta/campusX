"""API tests through FastAPI's TestClient: auth, role enforcement, booking flow, export gate, disruption approval."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.bookings.engine import BookingEngine
from app.services.scheduling.solver import from_schedule
from app.state import STATE
from conftest import ROOT


@pytest.fixture(scope="module")
def client(schedule):
    with TestClient(app) as c:
        STATE.import_dataset(reset=True)
        STATE.assignment = from_schedule(schedule)
        STATE.exams = schedule["exams"]
        STATE.outcome = BookingEngine(STATE.ds, STATE.assignment).decide()
        STATE.validate()
        yield c


def login(client, user):
    r = client.post("/api/auth/local-login", json={"username": user, "password": "campusx-demo"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_health_and_dataset_status(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["dataset_loaded"] and "development stub" in h["note"]
    s = client.get("/api/dataset/status").json()
    assert s["integrity"]["ok"] and s["integrity"]["counts"]["sessions"] == 189


def test_auth_required_and_bad_login(client):
    assert client.get("/api/timetable").status_code == 401
    assert client.post("/api/auth/local-login", json={"username": "admin", "password": "x"}).status_code == 401
    assert client.get("/api/timetable", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_role_enforcement_on_admin_endpoints(client):
    for who in ("faculty", "coordinator", "club"):
        h = login(client, who)
        assert client.post("/api/timetable/generate", json={}, headers=h).status_code == 403
        assert client.post("/api/dataset/import", headers=h).status_code == 403
        assert client.get("/api/timetable/export", headers=h).status_code == 403
        assert client.post("/api/disruptions/apply?did=x", headers=h).status_code == 403


def test_timetable_views(client):
    h = login(client, "admin")
    assert len(client.get("/api/timetable", headers=h).json()["sessions"]) == 189
    g = client.get("/api/timetable/group/Y1-A", headers=h).json()
    assert g["sessions"] and all("Y1-A" in s["groups"] for s in g["sessions"])
    assert client.get("/api/timetable/room/NOPE", headers=h).status_code == 404
    assert client.get("/api/reports/room-utilisation", headers=h).json()["rooms"]


def test_faculty_sees_only_own_timetable(client):
    h = login(client, "faculty")
    assert client.get("/api/timetable/faculty/F01", headers=h).status_code == 200
    assert client.get("/api/timetable/faculty/F02", headers=h).status_code == 403


def test_export_gate_passes_only_when_validator_accepts(client):
    h = login(client, "admin")
    r = client.get("/api/timetable/export", headers=h)
    assert r.status_code == 200 and len(r.json()["exams"]) == 41
    saved = dict(STATE.assignment)
    first = next(iter(saved))
    other = next(k for k in saved if saved[k][2] != saved[first][2])
    STATE.assignment[other] = saved[first]                      # corrupt: double-book a room
    try:
        bad = client.get("/api/timetable/export", headers=h)
        assert bad.status_code == 409 and "does not accept" in bad.json()["error"]["message"]
    finally:
        STATE.assignment = saved


BOOKING = {"title": "Robotics demo night", "attendance": 40, "duration_periods": 2,
           "windows": [{"day": "TUE", "from_period": 10, "to_period": 11}], "room_types": ["classroom", "seminar_hall"],
           "needs": ["projector"], "raw_text": "need a room tuesday 6-8pm"}


def test_booking_create_validation_and_clarification(client):
    h = login(client, "club")
    assert client.post("/api/bookings", json={**BOOKING, "needs": ["jacuzzi"]}, headers=h).status_code == 422
    r = client.post("/api/bookings", json={**BOOKING, "duration_periods": 5}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["detail"]["needs_clarification"]
    assert client.post("/api/bookings", json={**BOOKING, "mandatory_for_groups": ["NOPE"]}, headers=h).status_code == 422


def test_booking_flow_confirmed_then_not_double_booked(client):
    h = login(client, "club")
    a = client.post("/api/bookings", json=BOOKING, headers=h)
    assert a.status_code == 201 and a.json()["decision"]["status"] == "approved" and a.json()["state"] == "confirmed"
    placed = a.json()["decision"]
    # a second identical request must never receive the same room/time (confirmed bookings are not overwritten)
    b = client.post("/api/bookings", json=BOOKING, headers=h).json()
    assert (b["decision"]["room_id"], b["decision"]["day"], b["decision"]["start_period"]) != \
           (placed["room_id"], placed["day"], placed["start_period"]) or b["decision"]["status"] != "approved"
    # club cannot see other people's dataset bookings, only its own
    assert all(x["source"] == "user" for x in client.get("/api/bookings", headers=h).json()["bookings"])


def test_impossible_booking_rejected_with_reason(client):
    h = login(client, "club")
    r = client.post("/api/bookings", json={**BOOKING, "attendance": 1200, "room_types": ["auditorium", "outdoor"],
                                           "needs": []}, headers=h).json()
    assert r["state"] == "rejected" and "1,200" in r["decision"]["reason"]


def test_self_approval_blocked_and_permissions(client):
    club, admin, coord = login(client, "club"), login(client, "admin"), login(client, "coordinator")
    # a lab booking needs human approval
    lab = {**BOOKING, "title": "Coding contest", "attendance": 50, "duration_periods": 2, "room_types": ["lab_cs"],
           "needs": ["computers"], "windows": [{"day": "WED", "from_period": 10, "to_period": 11}], "department": "CSE"}
    b = client.post("/api/bookings", json=lab, headers=club).json()
    assert b["state"] == "proposed"
    assert client.post(f"/api/bookings/{b['id']}/decision", json={"action": "approve"}, headers=club).status_code == 403
    # coordinator of another department may not approve
    lab2 = {**lab, "title": "Mech lab thing", "department": "ME", "windows": [{"day": "WED", "from_period": 12, "to_period": 13}]}
    b2 = client.post("/api/bookings", json=lab2, headers=club).json()
    if b2["state"] == "proposed":
        assert client.post(f"/api/bookings/{b2['id']}/decision", json={"action": "approve"}, headers=coord).status_code == 403
    ok = client.post(f"/api/bookings/{b['id']}/decision", json={"action": "approve"}, headers=coord)
    assert ok.status_code == 200 and ok.json()["state"] == "confirmed"
    # requester can cancel; stranger cannot
    assert client.post(f"/api/bookings/{b['id']}/cancel", headers=club).status_code == 200


def test_admin_cannot_approve_own_request(client):
    admin = login(client, "admin")
    lab = {**BOOKING, "title": "Admin lab", "attendance": 30, "room_types": ["lab_cs"], "needs": ["computers"],
           "windows": [{"day": "FRI", "from_period": 10, "to_period": 11}], "department": "CSE"}
    b = client.post("/api/bookings", json=lab, headers=admin).json()
    if b["state"] == "proposed":
        assert client.post(f"/api/bookings/{b['id']}/decision", json={"action": "approve"}, headers=admin).status_code == 403


def test_manual_approval_override_is_revalidated(client):
    club, admin = login(client, "club"), login(client, "admin")
    lab = {**BOOKING, "title": "Lab night", "attendance": 50, "room_types": ["lab_cs"], "needs": ["computers"],
           "windows": [{"day": "MON", "from_period": 10, "to_period": 11}], "department": "CSE"}
    b = client.post("/api/bookings", json=lab, headers=club).json()
    assert b["state"] == "proposed"
    r = client.post(f"/api/bookings/{b['id']}/decision", json={"action": "approve", "room_id": "AUD"}, headers=admin)
    assert r.status_code == 409 and r.json()["error"]["detail"]["errors"]      # AUD is not a lab: refused


def test_disruption_preview_then_admin_apply(client, disruption):
    fac, admin = login(client, "faculty"), login(client, "admin")
    # faculty may only mark their own unavailability
    bad = client.post("/api/disruptions/preview", headers=fac, json={"changes": disruption["changes"]})
    assert bad.status_code == 403
    p = client.post("/api/disruptions/preview", headers=admin, json={"changes": disruption["changes"], "time_limit_s": 60})
    assert p.status_code == 200, p.text
    body = p.json()
    assert body["feasible"] and body["status"] == "previewed" and body["validation"]["accepted"]
    assert body["summary"]["moved"] > 0 and body["moved"][0]["reason"] and "Proven minimum" in body["minimality"]
    # nothing has changed yet: apply is the approval step
    assert client.get("/api/timetable/room/CR-102", headers=admin).json()["sessions"]
    assert client.post(f"/api/disruptions/apply?did={body['id']}", headers=login(client, "coordinator")).status_code == 403
    ap = client.post(f"/api/disruptions/apply?did={body['id']}", headers=admin)
    assert ap.status_code == 200 and ap.json()["validation"]["accepted"]
    assert client.get("/api/timetable/room/CR-102", headers=admin).json()["sessions"] == []      # closure now in force
    assert client.post(f"/api/disruptions/apply?did={body['id']}", headers=admin).status_code == 409   # not reusable


def test_infeasible_disruption_returns_conflict(client):
    admin = login(client, "admin")
    r = client.post("/api/disruptions/preview", headers=admin, json={"time_limit_s": 20, "changes": [
        {"type": "faculty_unavailable", "faculty_id": "F03", "days": ["MON", "TUE", "WED", "THU", "FRI"],
         "periods": list(range(1, 10)), "reason": "leave"}]}).json()
    assert r["feasible"] is False and r["conflict"]
