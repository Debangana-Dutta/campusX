"""OptiCampus Phase 2: booking-500 regression, migrations, real auth, password reset, persistence, notifications."""
import datetime as dt
import logging
import re
import sqlite3
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app.main import app
from app.models.db import Notification, PasswordReset, User, schema_drift, session_scope, BookingRecord
from app.services import accounts
from app.services.audit import notify
from app.state import STATE, AppState
from conftest import ROOT

PW = "campusx-demo"


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def login(c, who, pw=PW):
    r = c.post("/api/auth/login", json={"email": who if "@" in who else f"{who}@opticampus.demo", "password": pw})
    return r


def H(c, who):
    r = login(c, who)
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


# ------------------------------------------------------------------ the booking 500 and the migrations behind it
def _migrate(url, target="head"):
    env = {"DATABASE_URL": url, "PATH": "/usr/bin:/bin"}
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", target], cwd=ROOT / "backend", capture_output=True, text=True,
                       env={**env, "PYTHONPATH": str(ROOT / "backend")})
    assert r.returncode == 0, r.stderr[-800:]


def test_fresh_migrated_schema_has_no_drift_from_models(tmp_path):
    url = f"sqlite:///{tmp_path}/fresh.db"
    _migrate(url)
    assert schema_drift(create_engine(url)) == []


def test_stale_database_upgrades_to_models(tmp_path):
    """The original 500: a DB built from the first migration lacked notifications.kind/link. Upgrading must fix it."""
    url = f"sqlite:///{tmp_path}/stale.db"
    _migrate(url, "b8936abadf65")
    before = schema_drift(create_engine(url))
    assert any("notifications.kind" in p for p in before)              # reproduces the original defect
    _migrate(url)
    assert schema_drift(create_engine(url)) == []
    c = sqlite3.connect(tmp_path / "stale.db")
    c.execute("insert into notifications (user_id, message, kind, link, read, created_at) values ('u','m','booking','/x',0,'2026-01-01')")


BOOKING = {"title": "Quiz night", "attendance": 30, "duration_periods": 2, "room_types": ["classroom"],
           "windows": [{"day": "MON", "from_period": 12, "to_period": 13}]}


def test_booking_submission_returns_201_not_500(client):
    r = client.post("/api/bookings", json=BOOKING, headers=H(client, "club"))
    assert r.status_code == 201, r.text
    assert r.json()["id"].startswith("UR-") and r.json()["decision"]["status"] == "approved"


def test_booking_ids_do_not_collide(client):
    ids = {client.post("/api/bookings", json={**BOOKING, "title": f"Event {i}", "windows": [{"day": "TUE", "from_period": 10 + (i % 4), "to_period": 13}], "duration_periods": 1},
                       headers=H(client, "club")).json()["id"] for i in range(6)}
    assert len(ids) == 6


def test_failed_submission_leaves_no_half_saved_booking(client, monkeypatch):
    h = H(client, "club")
    with session_scope() as s:
        before = len(list(s.scalars(select(BookingRecord.id))))
    def boom(*a, **k):
        raise RuntimeError("simulated notification failure")
    monkeypatch.setattr(notify, "notify", boom)
    assert client.post("/api/bookings", json={**BOOKING, "title": "Atomic check"}, headers=h).status_code == 500
    with session_scope() as s:
        assert len(list(s.scalars(select(BookingRecord.id)))) == before         # rolled back together


# ------------------------------------------------------------------ authentication
def test_passwords_are_hashed_not_stored(client):
    with session_scope() as s:
        for u in s.scalars(select(User)):
            assert u.password_hash.startswith("scrypt$") and PW not in u.password_hash


def test_login_by_email_and_generic_errors(client):
    assert login(client, "admin@opticampus.demo").status_code == 200
    bad_pw, no_user = login(client, "admin", "wrong-password1"), login(client, "nobody@x.com", "wrong-password1")
    assert bad_pw.status_code == no_user.status_code == 401 and bad_pw.json() == no_user.json()      # no enumeration


def test_remember_me_issues_longer_token(client):
    from app.core.auth import _b64, _unb64
    import json
    def exp(remember):
        t = client.post("/api/auth/login", json={"email": "faculty@opticampus.demo", "password": PW, "remember": remember}).json()["token"]
        return json.loads(_unb64(t.split(".")[0]))["exp"]
    assert exp(True) - exp(False) > 20 * 24 * 3600


def test_request_access_rules_and_admin_review(client):
    body = {"name": "New Coordinator", "email": "coord.new@cit.ac.in", "password": "StrongPass123", "role": "department_coordinator", "department": "ME"}
    assert client.post("/api/auth/request-access", json={**body, "role": "admin"}).status_code == 403          # nobody requests Admin
    assert client.post("/api/auth/request-access", json={**body, "role": "wizard"}).status_code == 422
    assert client.post("/api/auth/request-access", json={**body, "email": "not-an-email"}).status_code == 422
    assert client.post("/api/auth/request-access", json={**body, "password": "short"}).status_code == 422
    assert client.post("/api/auth/request-access", json=body).status_code == 201
    assert client.post("/api/auth/request-access", json=body).status_code == 409                               # duplicate
    # pending: cannot sign in; admin is notified exactly once
    r = client.post("/api/auth/login", json={"email": body["email"], "password": body["password"]})
    assert r.status_code == 403 and "waiting for approval" in r.json()["error"]["message"]
    assert client.post("/api/auth/login", json={"email": body["email"], "password": "wrong-pass-123"}).status_code == 401
    n = client.get("/api/notifications", headers=H(client, "admin")).json()["items"]
    assert sum(body["email"] in i["message"] for i in n) == 1
    # only admins decide; the decision works
    assert client.post(f"/api/admin/accounts/{body['email']}/decision", json={"action": "approve"}, headers=H(client, "club")).status_code == 403
    assert client.post("/api/admin/accounts/admin@opticampus.demo/decision", json={"action": "approve"}, headers=H(client, "admin")).status_code in (403, 404)
    assert client.post(f"/api/admin/accounts/{body['email']}/decision", json={"action": "approve", "role": "admin"}, headers=H(client, "admin")).status_code == 422
    assert client.post(f"/api/admin/accounts/{body['email']}/decision", json={"action": "approve"}, headers=H(client, "admin")).status_code == 200
    ok = client.post("/api/auth/login", json={"email": body["email"], "password": body["password"]})
    assert ok.status_code == 200 and ok.json()["role"] == "department_coordinator"
    mine = client.get("/api/notifications", headers={"Authorization": "Bearer " + ok.json()["token"]}).json()["items"]
    assert any("approved" in i["message"] for i in mine)


def test_rejected_account_cannot_sign_in(client):
    b = {"name": "Reject Me", "email": "reject.me@cit.ac.in", "password": "StrongPass123", "role": "club_representative", "organisation": "X"}
    client.post("/api/auth/request-access", json=b)
    assert client.post(f"/api/admin/accounts/{b['email']}/decision", json={"action": "reject"}, headers=H(client, "admin")).status_code == 200
    assert login(client, b["email"], b["password"]).status_code in (401, 403)


def test_disabled_account_token_stops_working(client):
    h = H(client, "student")
    assert client.get("/api/notifications", headers=h).status_code == 200
    with session_scope() as s:
        s.get(User, "student@opticampus.demo").status = "disabled"
    assert client.get("/api/notifications", headers=h).status_code == 401
    with session_scope() as s:
        s.get(User, "student@opticampus.demo").status = "active"


# ------------------------------------------------------------------ forgot / reset / change password
def _reset_token(caplog, client, email):
    with caplog.at_level(logging.WARNING, logger="campusx.accounts"):
        r = client.post("/api/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    m = re.search(r"reset-password\?token=([\w-]+)", caplog.text)
    return r, (m.group(1) if m else None)


def test_forgot_password_is_identical_for_known_and_unknown_and_never_returns_token(client, caplog):
    r1, t1 = _reset_token(caplog, client, "faculty@opticampus.demo")
    caplog.clear()
    r2, t2 = _reset_token(caplog, client, "ghost@nowhere.com")
    assert r1.json() == r2.json() and t1 and t2 is None
    assert t1 not in r1.text                                                     # token only in the dev log / email


def test_reset_password_flow_single_use_and_invalidates_old_password(client, caplog):
    _, tok = _reset_token(caplog, client, "coordinator@opticampus.demo")
    assert client.post("/api/auth/reset-password", json={"token": tok, "new_password": "short"}).status_code == 422
    assert client.post("/api/auth/reset-password", json={"token": tok, "new_password": "BrandNewPass99"}).status_code == 200
    assert client.post("/api/auth/reset-password", json={"token": tok, "new_password": "AnotherPass99"}).status_code == 400   # single use
    assert login(client, "coordinator", PW).status_code == 401
    assert login(client, "coordinator", "BrandNewPass99").status_code == 200
    with session_scope() as s:                                                  # restore for other tests
        s.get(User, "coordinator@opticampus.demo").password_hash = accounts.hash_password(PW)


def test_expired_reset_token_rejected(client, caplog):
    _, tok = _reset_token(caplog, client, "club@opticampus.demo")
    with session_scope() as s:
        for r in s.scalars(select(PasswordReset)):
            r.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    assert client.post("/api/auth/reset-password", json={"token": tok, "new_password": "BrandNewPass99"}).status_code == 400
    assert client.post("/api/auth/reset-password", json={"token": "x" * 40, "new_password": "BrandNewPass99"}).status_code == 400


def test_reset_tokens_are_stored_hashed(client, caplog):
    _, tok = _reset_token(caplog, client, "faculty@opticampus.demo")
    with session_scope() as s:
        assert all(tok not in r.token_hash and len(r.token_hash) == 64 for r in s.scalars(select(PasswordReset)))


def test_change_password(client):
    h = H(client, "faculty")
    assert client.post("/api/auth/change-password", json={"current_password": "wrong-one-1", "new_password": "NewerPass123"}, headers=h).status_code == 403
    assert client.post("/api/auth/change-password", json={"current_password": PW, "new_password": "weak"}, headers=h).status_code == 422
    assert client.post("/api/auth/change-password", json={"current_password": PW, "new_password": "NewerPass123"}, headers=h).status_code == 200
    assert login(client, "faculty", "NewerPass123").status_code == 200 and login(client, "faculty", PW).status_code == 401
    with session_scope() as s:
        s.get(User, "faculty@opticampus.demo").password_hash = accounts.hash_password(PW)


# ------------------------------------------------------------------ persistence across restart
def test_state_and_bookings_survive_a_restart(client):
    h = H(client, "club")
    bid = client.post("/api/bookings", json={**BOOKING, "title": "Persistence check", "windows": [{"day": "WED", "from_period": 12, "to_period": 13}]}, headers=h).json()["id"]
    STATE.save()
    fresh = AppState()                       # what a restarted process does
    fresh.import_dataset()
    assert fresh.assignment == STATE.assignment and fresh.exams == STATE.exams
    assert [d.as_dict() for d in fresh.outcome.decisions] == [d.as_dict() for d in STATE.outcome.decisions]
    assert fresh.status() == STATE.status()
    assert client.get(f"/api/bookings/{bid}", headers=h).json()["request"]["title"] == "Persistence check"   # DB row


# ------------------------------------------------------------------ notifications
def test_notifications_only_reach_intended_recipients_and_dedupe(client):
    key = "test-dedupe-1"
    assert notify.notify("faculty@opticampus.demo", "Only for faculty", "info", sender="admin", related_id="X1", dedupe=key)
    assert not notify.notify("faculty@opticampus.demo", "Only for faculty", "info", dedupe=key)       # same event, once
    mine = client.get("/api/notifications", headers=H(client, "faculty")).json()["items"]
    assert sum(i["message"] == "Only for faculty" for i in mine) == 1
    assert next(i for i in mine if i["message"] == "Only for faculty")["related_id"] == "X1"
    assert all(i["message"] != "Only for faculty" for i in client.get("/api/notifications", headers=H(client, "club")).json()["items"])
