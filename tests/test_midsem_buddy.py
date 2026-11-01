"""Campus Buddy exam answers: the reported 'midsem' failures, publish workflow, student scoping, no invented dates."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import User, session_scope
from app.services import accounts
from app.state import STATE

PW = "campusx-demo"


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.post("/api/admin/demo-reset", headers=H(c, "admin@opticampus.demo")).json()["reset"]
        with session_scope() as s:             # extra accounts: a CSE-3 student (has a database exam) and a student with no group
            for email, gid in (("s3@opticampus.demo", "CSE-3"), ("nogroup@opticampus.demo", None)):
                if not s.get(User, email):
                    s.add(User(id=email, email=email, name=email.split("@")[0], role="student", status="active", group_id=gid,
                               department="CSE", password_hash=accounts.hash_password(PW)))
        yield c


def H(c, email):
    return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": email, "password": PW}).json()["token"]}


def ask(c, who, q, **extra):
    return c.post("/api/buddy/ask", headers=H(c, who), json={"question": q, **extra}).json()


MIDSEM_QUESTIONS = ["When is my midsem?", "When is my next exam?", "What is my examination timetable?", "Where is my examination?",
                    "What exams do I have next week?", "Mera midsem kab hai?", "Exam kab hai?", "Mera next paper kaunsa hai?", "mid sem kab hai", "midterm schedule"]


@pytest.mark.parametrize("q", MIDSEM_QUESTIONS)
def test_every_midsem_phrasing_returns_real_exam_details_for_a_student(client, q):
    r = ask(client, "student@opticampus.demo", q)
    assert r["intent"] == "exam", r
    mine = [e for e in STATE.exams if "CSE-2" in STATE.ds.exams[e["exam_id"]]["groups"]]
    assert mine and r["facts"]["exams"], r
    ans = r["answer"]
    e = r["facts"]["exams"][0]
    assert e["course"] in ans and e["day"] in ans and e["start"] in ans and e["end"] in ans          # course NAME, day, times
    assert all(room in ans for room in e["rooms"]) and f"{e['duration_hours']} h" in ans              # venue + duration
    assert "I have no exam entries" not in ans
    assert {x["exam"] for x in r["facts"]["exams"]} <= {e["exam_id"] for e in mine}                  # only this student's group


def test_answers_match_the_database_exactly(client):
    r = ask(client, "student@opticampus.demo", "What is my examination timetable?")
    slot = {s["id"]: s for s in STATE.ds.raw["calendar"]["exam_week"]["sessions"]}
    expect = {e["exam_id"]: (e["day"], slot[e["session"]]["start"], tuple(e["rooms"])) for e in STATE.exams if "CSE-2" in STATE.ds.exams[e["exam_id"]]["groups"]}
    got = {x["exam"]: (x["day"], x["start"], tuple(x["rooms"])) for x in r["facts"]["exams"]}
    assert got == expect


def test_course_specific_hinglish_question_uses_the_named_course(client):
    r = ask(client, "s3@opticampus.demo", "DBMS ka exam kab hai?")
    assert "Database Systems" in r["answer"] and len(r["facts"]["exams"]) == 1
    r2 = ask(client, "s3@opticampus.demo", "Mera DBMS midsem kab hai?")
    assert r2["facts"]["exams"][0]["course"] == "Database Systems"
    r3 = ask(client, "s3@opticampus.demo", "When is my DBMS midsem?")
    assert r3["facts"]["exams"][0]["exam"] == r["facts"]["exams"][0]["exam"]


def test_course_the_student_has_no_exam_for_is_explained(client):
    r = ask(client, "student@opticampus.demo", "When is my DBMS midsem?")                         # CSE-2 has no database exam
    assert "can't find" in r["answer"] and "exams I have for group CSE-2" in r["answer"] and not r["facts"].get("exams")


def test_tomorrow_question_does_not_invent_dates(client):
    r = ask(client, "student@opticampus.demo", "Kal mera koi exam hai?")
    assert "can't tell whether tomorrow falls in exam week" in r["answer"] and r["facts"]["exams"]
    assert "calendar dates" in r["answer"]


def test_day_filter(client):
    ex = ask(client, "student@opticampus.demo", "midsem")["facts"]["exams"]
    day = ex[0]["day"]
    names = {"MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday"}
    r = ask(client, "student@opticampus.demo", f"Do I have a midsem on {names[day]}?")
    assert {x["day"] for x in r["facts"]["exams"]} == {day}


def test_student_without_a_group_gets_an_explanation(client):
    r = ask(client, "nogroup@opticampus.demo", "When is my midsem?")
    assert "not linked to a student group" in r["answer"]


def test_faculty_gets_exams_of_courses_they_teach_not_a_generic_empty_reply(client):
    r = ask(client, "faculty@opticampus.demo", "Exam kab hai?")
    assert "I have no exam entries" not in r["answer"] and r["facts"]["scope"] == "the courses you teach"
    taught = {s["course_id"] for s in STATE.ds.sessions.values() if s["faculty_id"] == "F01"}
    for x in r["facts"].get("exams", []):
        assert set(STATE.ds.exams[x["exam"]]["course_ids"]) & taught


def test_club_rep_is_told_why_there_is_no_personal_exam(client):
    r = ask(client, "club@opticampus.demo", "When is my midsem?")
    assert "doesn't have personal exams" in r["answer"]


def test_students_cannot_ask_about_another_group(client):
    r = ask(client, "student@opticampus.demo", "When is my midsem?", group_id="ME-3")
    assert r["facts"]["scope"] == "group CSE-2"


# ------------------------------------------------------------------ publish workflow
def test_unpublished_exams_are_hidden_from_students_with_a_clear_message(client):
    a, st = H(client, "admin@opticampus.demo"), H(client, "student@opticampus.demo")
    assert client.post("/api/exams/publish", json={"withdraw": True}, headers=a).json()["published"] is False
    r = ask(client, "student@opticampus.demo", "When is my midsem?")
    assert r["answer"].startswith("No midsem examinations have been published for your group yet. Please check again after the examination timetable is released.")
    api = client.get("/api/exams", headers=st).json()
    assert api["exams"] == [] and api["published"] is False and "published" in api["note"]
    assert client.get("/api/exams", headers=a).json()["exams"]                                       # admin still sees the draft
    assert client.post("/api/exams/publish", headers=st).status_code == 403                          # only admin publishes
    assert client.post("/api/exams/publish", headers=a).json()["published"] is True
    assert ask(client, "student@opticampus.demo", "When is my midsem?")["facts"]["exams"]
    n = client.get("/api/notifications", headers=st).json()["items"]
    assert any("published" in i["message"] and i["kind"] == "exam" for i in n)


def test_regenerating_exams_returns_them_to_draft(client):
    a = H(client, "admin@opticampus.demo")
    assert client.post("/api/exams/generate?time_limit_s=10", headers=a).status_code == 200
    assert STATE.exams_published is False
    assert "published" in ask(client, "student@opticampus.demo", "Exam kab hai?")["answer"]
    assert client.post("/api/exams/publish", headers=a).json()["published"] is True              # validated, then published again


def test_publish_state_survives_restart(client):
    from app.state import AppState
    STATE.save()
    fresh = AppState(); fresh.import_dataset()
    assert fresh.exams_published == STATE.exams_published is True
