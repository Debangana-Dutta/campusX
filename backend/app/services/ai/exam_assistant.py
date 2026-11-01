"""Exam answers for Campus Buddy, built from the real exam schedule (never invented).

Resolution order: is anything created? published? is the user linked to a group/courses? which exams match
(group/courses, optional course named in the question, optional day)? Every empty result gets a specific explanation.
The dataset's exam week has weekday names only (no calendar dates), so answers give the day and slot and say so.
"""
from __future__ import annotations

import re
from typing import Any

ALIASES = {"dbms": "database", "os": "operating", "cn": "network", "dsa": "data structures", "ds": "data structures",
           "ml": "machine learning", "ai": "artificial", "coa": "computer organi", "toc": "theory of computation", "se": "software engineering"}
DAY_WORDS = {"monday": "MON", "mon": "MON", "tuesday": "TUE", "tue": "TUE", "wednesday": "WED", "wed": "WED",
             "thursday": "THU", "thu": "THU", "friday": "FRI", "fri": "FRI", "saturday": "SAT", "sat": "SAT"}


def _named_course(q: str, ds, pool: set[str]) -> tuple[str | None, list[str]]:
    """Course the user named (code, title words or an abbreviation like DBMS) -> (label, matching course ids among ALL courses)."""
    t = q.lower()
    hits: list[str] = []
    label = None
    for code in re.findall(r"\b[a-z]{2,3}\d{3}\b", t):
        if code.upper() in ds.courses:
            hits.append(code.upper()); label = ds.courses[code.upper()]["title"]
    for ab, needle in ALIASES.items():
        if re.search(rf"\b{ab}\b", t):
            for cid, c in ds.courses.items():
                if needle in c["title"].lower():
                    hits.append(cid); label = label or needle.title()
    if not hits:
        for cid, c in ds.courses.items():
            words = [w for w in re.findall(r"[a-z]{4,}", c["title"].lower()) if w not in ("lab", "systems", "introduction", "engineering", "design")]
            if words and all(w in t for w in words[:2]):
                hits.append(cid); label = c["title"]
    return label, list(dict.fromkeys(hits))


def answer(question: str, user, ds, exams: list[dict] | None, published: bool, *, group_id: str | None = None) -> dict[str, Any]:
    cal = ds.raw["calendar"]["exam_week"]
    slot = {s["id"]: s for s in cal["sessions"]}
    day_order = {d: i for i, d in enumerate(cal["days"])}
    facts: dict[str, Any] = {"published": published}
    is_admin = user.role == "admin"

    if not exams:
        return {"answer": "The examination timetable has not been created yet. It will appear here once the admin office generates and publishes it.", "facts": facts}
    if not published and not is_admin:
        return {"answer": "No midsem examinations have been published for your group yet. Please check again after the examination timetable is released.", "facts": facts}

    # ---- whose exams?
    who, mine = "", []
    gid = user.group_id if user.role == "student" else group_id
    if user.role == "student" and not gid:
        return {"answer": "Your account is not linked to a student group, so I can't look up your exams. Please ask the admin office to link your group.", "facts": facts}
    if gid:
        if gid not in ds.groups:
            return {"answer": f"I don't know a student group called {gid}.", "facts": facts}
        mine, who = [e for e in exams if gid in ds.exams[e["exam_id"]]["groups"]], f"group {gid}"
    elif user.role == "faculty":
        taught = {s["course_id"] for s in ds.sessions.values() if s["faculty_id"] == user.faculty_id}
        mine, who = [e for e in exams if set(ds.exams[e["exam_id"]]["course_ids"]) & taught], "the courses you teach"
    elif user.role in ("admin", "department_coordinator"):
        mine, who = list(exams), "all groups"
    else:
        return {"answer": "Exam timetables are shown to students (by group), faculty (for the courses they teach) and the admin office. Your role doesn't have personal exams.", "facts": facts}
    facts["scope"] = who

    # ---- optional course / day filters
    asked_label, course_ids = _named_course(question, ds, set())
    shown = mine
    if course_ids:
        shown = [e for e in mine if set(ds.exams[e["exam_id"]]["course_ids"]) & set(course_ids)]
        if not shown:
            names = "; ".join(f"{_title(ds, e)} ({e['day']} {slot[e['session']]['start']}-{slot[e['session']]['end']})" for e in sorted(mine, key=lambda e: (day_order[e["day"]], e["session"])))
            return {"answer": f"I can't find a {asked_label} midsem among the published exams for {who}. " + (f"The exams I have for {who}: {names}." if names else f"There are no published exams for {who}."), "facts": facts}
    t = question.lower()
    wanted_days = [d for w, d in DAY_WORDS.items() if re.search(rf"\b{w}\b", t)]
    if wanted_days:
        shown = [e for e in shown if e["day"] in wanted_days]
    if not mine:
        return {"answer": f"No midsem examinations have been published for {who} yet. Please check again after the examination timetable is released.", "facts": facts}
    if not shown:
        return {"answer": f"No exam for {who} falls on {', '.join(wanted_days)}. Your exam days: " + ", ".join(sorted({e['day'] for e in mine}, key=day_order.get)) + ".", "facts": facts}

    shown = sorted(shown, key=lambda e: (day_order[e["day"]], e["session"]))
    def line(e):
        sl = slot[e["session"]]; rec = ds.exams[e["exam_id"]]
        return (f"{_title(ds, e)} ({e['exam_id'].replace('EX-', '')}): {e['day']} {sl['start']}-{sl['end']} ({rec['duration_hours']} h), "
                f"venue {', '.join(e['rooms'])}")
    facts["exams"] = [{"exam": e["exam_id"], "course": _title(ds, e), "day": e["day"], "start": slot[e["session"]]["start"], "end": slot[e["session"]]["end"],
                       "duration_hours": ds.exams[e["exam_id"]]["duration_hours"], "rooms": e["rooms"]} for e in shown]
    note = ("Midsems run in the exam week right after teaching Week 7; the dataset gives weekdays and slots, not calendar dates. "
            "Seats are allocated at half room capacity, so check the notice board for your exact seat.")
    nxt = re.search(r"next|agla|agli|pehla|first|kaunsa|upcoming", t) is not None
    tomorrow = re.search(r"\bkal\b|tomorrow|\baaj\b|today", t) is not None
    if nxt and not course_ids:
        head = f"Your next exam is {line(shown[0])}."
        if len(shown) > 1:
            head += f" After that: " + "; ".join(line(e) for e in shown[1:]) + "."
    elif course_ids and len(shown) == 1:
        head = f"Your {asked_label} midsem: {line(shown[0])}."
    else:
        head = f"Published midsem exams for {who} ({len(shown)}): " + "; ".join(line(e) for e in shown) + "."
    if tomorrow:
        head = ("I can't tell whether tomorrow falls in exam week, because exams here are scheduled by weekday, not calendar date. " + head)
    return {"answer": f"{head} {note}", "facts": facts}


def _title(ds, e) -> str:
    return " / ".join(ds.courses[c]["title"] for c in ds.exams[e["exam_id"]]["course_ids"] if c in ds.courses)
