"""Faculty scheduling assistant: parsing, valid alternatives, independent validation, no-solution reports, approval architecture."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai import faculty_assistant as fa
from app.services.validation.runner import run_validator_on_dataset
from app.state import STATE

PW = "campusx-demo"
MON = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))


def H(c, who):
    return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": f"{who}@opticampus.demo", "password": PW}).json()["token"]}


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.post("/api/admin/demo-reset", headers=H(c, "admin")).json()["reset"]
        yield c


def my_sessions():
    return {sid: v for sid, v in STATE.assignment.items() if STATE.ds.sessions[sid]["faculty_id"] == "F01"}


def a_teaching_day():
    day = sorted({v[0] for sid, v in my_sessions().items() if not STATE.ds.sessions[sid]["basket_slot"]}, key=["MON", "TUE", "WED", "THU", "FRI"].index)[0]
    return day, {"MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday", "FRI": "Friday"}[day]


# ------------------------------------------------------------------ interpretation (structured request)
def test_interpret_unavailability_leave_and_periods(client):
    ds = STATE.ds
    a = fa.interpret("I am on leave tomorrow", ds, "F01", STATE.assignment, MON)
    assert a["unavailable"]["days"] == ["TUE"] and a["unavailable"]["periods"] == list(range(1, 10))
    b = fa.interpret("I am unavailable on Wednesday morning because of a conference", ds, "F01", STATE.assignment, MON)
    assert b["unavailable"]["days"] == ["WED"] and b["unavailable"]["periods"] == [1, 2, 3, 4, 5]
    assert fa.interpret("I cannot teach", ds, "F01", STATE.assignment, MON)["follow_up"]               # which day?
    assert fa.interpret("hello there", ds, "F01", STATE.assignment, MON)["follow_up"]


def test_interpret_move_with_source_and_target(client):
    ds = STATE.ds
    sid, (d, p, _) = next((s, v) for s, v in my_sessions().items() if ds.sessions[s]["kind"] == "lecture" and not ds.sessions[s]["basket_slot"])
    title = ds.courses[ds.sessions[sid]["course_id"]]["title"]
    names = {"MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday", "FRI": "Friday"}
    it = fa.interpret(f"Move my {title} lecture from {names[d]} P{p} to Friday P4", ds, "F01", STATE.assignment, MON)
    assert [t["sid"] for t in it["targets"]] == [sid] and it["targets"][0]["to"] == ("FRI", 4)


# ------------------------------------------------------------------ valid alternatives, validated independently, nothing applied
def test_leave_day_returns_validated_alternatives_and_changes_nothing(client):
    fac = H(client, "faculty")
    day, name = a_teaching_day()
    before = dict(STATE.assignment)
    r = client.post("/api/assistant/schedule-request", json={"text": f"I am unavailable on {name} because I have to attend a conference"}, headers=fac).json()
    assert r["alternatives"], r
    p = r["proposal"]
    assert p["feasible"] and p["validation"]["accepted"] and p["validation"]["hard_violation_count"] == 0       # official validator accepted the whole result
    assert {m["session_id"] for m in p["moved"]} == set(r["alternatives"]) and all(m["from"]["day"] == day for m in p["moved"])
    assert "schedule_after" not in p                                                                         # internal object never leaves the server
    for sid, alts in r["alternatives"].items():
        for a in alts:
            assert a["day"] != day and a["explanation"]                                                      # moved off the unavailable day, with reasons
    assert STATE.assignment == before                                                                        # drafting NEVER touches the timetable


def test_every_offered_alternative_passes_the_official_validator_on_its_own(client):
    fac = H(client, "faculty")
    day, name = a_teaching_day()
    r = client.post("/api/assistant/schedule-request", json={"text": f"I am on leave on {name}"}, headers=fac).json()
    sid, alts = next(iter(r["alternatives"].items()))
    change = r["interpretation"]["unavailable"]
    from app.services.dataset.loader import apply_disruption
    from app.services.scheduling.solver import to_schedule_sessions
    from app.services.pipeline import assemble_schedule
    new_raw = apply_disruption(STATE.live_raw, {"changes": [change]})
    from app.services.dataset.loader import Dataset
    from app.services.bookings.engine import BookingEngine
    for a in alts:
        asg = dict(STATE.assignment); asg[sid] = (a["day"], a["start_period"], a["room_id"])
        # only this one session is moved; the others on the unavailable day may still be affected, so validate the single-move effect on hard rules other than H7 of those
        sched = assemble_schedule("t", STATE.live_raw["dataset_id"], asg, BookingEngine(Dataset(new_raw), asg).decide(), STATE.exams)
        v = run_validator_on_dataset(new_raw, sched).summary()
        broke = {x["detail"] for x in v["hard_violations"] if sid in x["detail"]}
        assert not broke, broke


def test_explicit_move_to_a_clashing_slot_is_refused_with_the_reason(client):
    fac = H(client, "faculty")
    mine = my_sessions()
    ds = STATE.ds
    (s1, (d1, p1, _)) = next((s, v) for s, v in mine.items() if ds.sessions[s]["kind"] == "lecture" and not ds.sessions[s]["basket_slot"])
    (s2, (d2, p2, _)) = next((s, v) for s, v in mine.items() if s != s1 and ds.sessions[s]["duration"] == 1 and v[:2] != (d1, p1))
    names = {"MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday", "FRI": "Friday"}
    title = ds.courses[ds.sessions[s1]["course_id"]]["title"]
    r = client.post("/api/assistant/schedule-request", json={"text": f"Move my {title} lecture from {names[d1]} P{p1} to {names[d2]} P{p2}"}, headers=fac).json()
    ns = [n for n in r["no_solution"] if n["session_id"] == s1]
    assert ns and ns[0]["asked"] == f"{d2} P{p2}" and "faculty" in ns[0]["why_not"].lower()                   # F01 is already teaching then
    assert r["alternatives"].get(s1)                                                                        # and other valid options are still offered


def test_no_solution_report_names_sessions_constraints_and_rejected_slots(client):
    fac = H(client, "faculty")
    r = client.post("/api/assistant/schedule-request", json={"text": "I am unavailable on Monday Tuesday Wednesday Thursday Friday"}, headers=fac).json()
    assert r["interpretation"]["unavailable"]["days"] == ["MON", "TUE", "WED", "THU", "FRI"]
    ns = r["no_solution"]
    assert not r["alternatives"] and r["proposal"] is None                                                  # nothing valid exists: nothing is proposed
    assert {n["session_id"] for n in ns} >= {sid for sid, v in my_sessions().items() if not STATE.ds.sessions[sid]["basket_slot"]}
    for n in ns:
        assert n["affected_sessions"] == [n["session_id"]] and "No valid day/period/room" in n["why_not"]
        assert n["removed_by_hard_rules"].get("faculty_unavailable", 0) > 0                                 # the unavailable slots, by name
        assert "rejected_slots_by_constraint" in n


# ------------------------------------------------------------------ submit -> admin approval -> transaction
def test_submit_saves_a_proposal_and_leaves_the_timetable_unchanged_until_admin_approves(client):
    fac, adm, co = H(client, "faculty"), H(client, "admin"), H(client, "coordinator")
    day, name = a_teaching_day()
    before = dict(STATE.assignment)
    text = f"I am unavailable on {name} because I have to attend a conference"
    s = client.post("/api/assistant/submit", json={"text": text, "schedule_after": {"sessions": []}, "moved": []}, headers=fac)   # extra client fields are ignored
    assert s.status_code == 200, s.text
    did = s.json()["id"]
    assert STATE.assignment == before                                                                        # still unchanged
    assert any(did in i["message"] for i in client.get("/api/notifications", headers=adm).json()["items"])
    assert any(did in i["message"] for i in client.get("/api/notifications", headers=co).json()["items"])
    assert not any(did in i["message"] for i in client.get("/api/notifications", headers=H(client, "club")).json()["items"])
    # faculty cannot approve their own request; only the admin can
    assert client.post(f"/api/disruptions/apply?did={did}", headers=fac).status_code == 403
    assert STATE.assignment == before
    cmp_ = client.get(f"/api/disruptions/{did}/comparison", headers=adm).json()
    assert cmp_["status"] == "previewed" and cmp_["proposal"]["validation"]["accepted"] and cmp_["proposal"]["moved"]
    # requester sees own request, others do not
    assert any(d["id"] == did for d in client.get("/api/disruptions", headers=fac).json()["disruptions"])
    assert client.get(f"/api/disruptions/{did}/comparison", headers=H(client, "student")).status_code in (403, 404)
    ap = client.post(f"/api/disruptions/apply?did={did}", headers=adm)
    assert ap.status_code == 200 and ap.json()["validation"]["accepted"]
    moved = {m["session_id"]: m["to"] for m in cmp_["proposal"]["moved"]}
    for sid, to in moved.items():
        assert STATE.assignment[sid] == (to["day"], to["start_period"], to["room_id"])                      # applied exactly as proposed
    assert not any(v[0] == day for sid, v in STATE.assignment.items() if STATE.ds.sessions[sid]["faculty_id"] == "F01")   # F01 now free that day
    assert any("approved and applied" in i["message"] for i in client.get("/api/notifications", headers=fac).json()["items"])
    assert client.post(f"/api/disruptions/apply?did={did}", headers=adm).status_code == 409                   # not re-appliable


def test_stale_proposal_is_not_applied_after_the_timetable_changes(client):
    assert client.post("/api/admin/demo-reset", headers=H(client, "admin")).json()["reset"]
    fac, adm = H(client, "faculty"), H(client, "admin")
    day, name = a_teaching_day()
    did = client.post("/api/assistant/submit", json={"text": f"I am unavailable on {name}"}, headers=fac).json()["id"]
    # the admin applies a different change first, so the baseline the proposal was built on is gone
    other = client.post("/api/disruptions/preview", headers=adm, json={"changes": [{"type": "faculty_unavailable", "faculty_id": "F02", "days": ["FRI"], "periods": [1, 2]}], "time_limit_s": 30}).json()
    assert client.post(f"/api/disruptions/apply?did={other['id']}", headers=adm).status_code == 200
    r = client.post(f"/api/disruptions/apply?did={did}", headers=adm)
    assert r.status_code == 409 and "changed since this preview" in r.json()["error"]["message"]


def test_assistant_permissions_and_privacy(client):
    for who in ("student", "club", "coordinator", "admin"):
        assert client.post("/api/assistant/schedule-request", json={"text": "I am unavailable on Monday"}, headers=H(client, who)).status_code == 403
        assert client.post("/api/assistant/submit", json={"text": "I am unavailable on Monday"}, headers=H(client, who)).status_code == 403
    assert client.post("/api/assistant/schedule-request", json={"text": "hi"}, headers=H(client, "faculty")).status_code == 422
    # a faculty member only ever sees their OWN sessions in alternatives
    r = client.post("/api/assistant/schedule-request", json={"text": "Move my Database Systems lecture"}, headers=H(client, "faculty")).json()
    assert all(STATE.ds.sessions[s]["faculty_id"] == "F01" for s in r["alternatives"])
    assert any(a["action"] == "assistant.submit" for a in client.get("/api/admin/audit", headers=H(client, "admin")).json()["events"])


def test_unclear_requests_get_follow_up_questions_not_guesses(client):
    r = client.post("/api/assistant/schedule-request", json={"text": "I need some changes to my schedule please"}, headers=H(client, "faculty")).json()
    assert r["follow_up"] and not r["alternatives"] and r["proposal"] is None


# ------------------------------------------------------------------ regression: assistant 500 / misleading "need more info"
def test_unknown_faculty_link_is_a_clear_409_not_a_500(client):
    """An account whose faculty_id is not in the dataset used to crash with 'internal server error'."""
    from app.models.db import User as DbUser, session_scope
    from app.services.accounts import hash_password
    with session_scope() as s:
        s.add(DbUser(id="ghost@opticampus.demo", email="ghost@opticampus.demo", name="Ghost Faculty", role="faculty", status="active",
                     password_hash=hash_password("Ghost-pass-123"), department="CSE", faculty_id="F99"))
    tok = client.post("/api/auth/login", json={"email": "ghost@opticampus.demo", "password": "Ghost-pass-123"}).json()["token"]
    r = client.post("/api/assistant/schedule-request", json={"text": "I am unavailable on Wednesday because I have to attend a conference."},
                    headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 409, r.text
    assert "F99" in r.json()["error"]["message"] and "Admin" in r.json()["error"]["message"]
    r2 = client.post("/api/assistant/submit", json={"text": "I am unavailable on Wednesday"}, headers={"Authorization": "Bearer " + tok})
    assert r2.status_code == 409


def test_status_distinguishes_question_from_nothing_to_move_from_options(client):
    fac = H(client, "faculty")
    day, name = a_teaching_day()
    ok = client.post("/api/assistant/schedule-request", json={"text": f"I am unavailable on {name}"}, headers=fac).json()
    assert ok["status"] == "options" and ok["alternatives"]
    q = client.post("/api/assistant/schedule-request", json={"text": "I cannot teach at all"}, headers=fac).json()
    assert q["status"] == "needs_info" and q["follow_up"]
    free = next(d for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"] if d != name and not any(
        v[0] == d[:3].upper() for v in my_sessions().values()))  if any(
        not any(v[0] == d[:3].upper() for v in my_sessions().values()) for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]) else None
    if free:
        n = client.post("/api/assistant/schedule-request", json={"text": f"I am unavailable on {free}"}, headers=fac).json()
        assert n["status"] == "nothing_to_move" and not n["follow_up"] and "nothing needs to move" in n["message"]


def test_malformed_choices_are_422(client):
    r = client.post("/api/assistant/schedule-request", json={"text": "I am unavailable on Monday", "choices": {"X": "abc"}}, headers=H(client, "faculty"))
    assert r.status_code == 422


# ------------------------------------------------------------------ parser coverage added in the Hinglish / phrasing pass
# NOTE: written without being able to run pytest in the authoring sandbox; run `pytest tests/test_faculty_assistant.py` locally.
def test_interpret_hinglish_leave_and_move(client):
    ds = STATE.ds
    a = fa.interpret("Mujhe Wednesday ko leave chahiye, meri classes reschedule kar do.", ds, "F01", STATE.assignment, MON)
    assert a["unavailable"]["days"] == ["WED"] and not a["targets"] and not a["follow_up"]      # the leave is the request; no bogus "which class?"
    b = fa.interpret("Kal meri class nahi ho payegi, koi alternative slot find karo.", ds, "F01", STATE.assignment, MON)
    assert b["unavailable"]["days"] == ["TUE"]                                                    # MON is a Monday -> kal = Tuesday
    c = fa.interpret("Mera Monday ka lecture Tuesday ko shift karna hai.", ds, "F01", STATE.assignment, MON)
    assert c["targets"] and all(t["to"][0] == "TUE" and t["to"][1] is None for t in c["targets"])


def test_interpret_day_only_target_does_not_crash_and_extra_session_is_not_faked(client):
    ds = STATE.ds
    it = fa.interpret("Move my lecture to Friday", ds, "F01", STATE.assignment, MON)             # used to raise TypeError (int(None))
    assert it["follow_up"] or all(t["to"][0] == "FRI" for t in it["targets"])
    x = fa.interpret("Add an extra tutorial for Database Management Systems.", ds, "F01", STATE.assignment, MON)
    assert x["unsupported"] == "add_session" and not x["targets"] and not x["unavailable"]


def test_room_problem_is_not_read_as_faculty_unavailable(client):
    it = fa.interpret("The room assigned to my lab is unavailable. Find another suitable room.", STATE.ds, "F01", STATE.assignment, MON)
    assert it["room_problem"] and it["unavailable"] is None


def test_extra_session_request_returns_not_supported_status_over_http(client):
    r = client.post("/api/assistant/schedule-request", json={"text": "Add an extra tutorial for my class next week"}, headers=H(client, "faculty")).json()
    assert r["status"] == "not_supported" and not r["alternatives"] and r["proposal"] is None
