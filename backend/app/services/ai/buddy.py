"""Campus Buddy: grounded timetable assistant (English + Hinglish).

1. The backend works out WHO is asking and which rows they may see (student -> own group, faculty -> own classes).
2. A deterministic engine computes the answer from real timetable/exam/change data -> `facts` + `answer`.
3. If Gemini is configured it may only REPHRASE those facts in the user's language; if it fails (or the key is
   missing) the deterministic answer is returned and `ai_used` is false. Gemini never sees other users' data.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

from app.core.auth import User
from app.services.ai import gemini

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
PY_DAY = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
DAYWORDS = {"mon": "MON", "tue": "TUE", "wed": "WED", "thu": "THU", "fri": "FRI", "sat": "SAT", "sun": "SUN"}


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def _period_times(cal: dict) -> dict[int, tuple[str, str]]:
    return {p["id"]: (p["start"], p["end"]) for p in cal["periods"]}


def _fmt(s: dict, entry: tuple, ds, pt) -> str:
    d, p, r = entry
    a, b = pt[p][0], pt[p + s["duration"] - 1][1]
    fac = ds.faculty[s["faculty_id"]]["name"]
    title = ds.courses[s["course_id"]]["title"]
    return f"{title} ({s['kind']}) {a}-{b} in {r} with {fac}"


def _scope_sessions(user: User, ds, assign, group_id=None, faculty_id=None) -> tuple[list[str], str]:
    if user.role == "student":
        g = user.group_id
        return [sid for sid, s in ds.sessions.items() if g in s["groups"]], f"group {g}"
    if user.role == "faculty" and user.faculty_id:
        return [sid for sid, s in ds.sessions.items() if s["faculty_id"] == user.faculty_id], f"faculty {user.faculty_id}"
    if user.role in ("admin", "department_coordinator"):
        if group_id in ds.groups:
            return [sid for sid, s in ds.sessions.items() if group_id in s["groups"]], f"group {group_id}"
        if faculty_id in ds.faculty:
            return [sid for sid, s in ds.sessions.items() if s["faculty_id"] == faculty_id], f"faculty {faculty_id}"
    return [], ""


def _intent(q: str) -> str:
    t = q.lower()
    if re.search(r"exam|pariksha|test\b|paper", t):
        return "exam"
    if re.search(r"who (is )?teach|kaun pad|teacher|professor|faculty|sir\b|madam", t):
        return "teacher"
    if re.search(r"chang|badal|moved|shift|update", t):
        return "changes"
    if re.search(r"free (period|slot|hour)|khali|free hai|gap", t):
        return "free"
    if re.search(r"next|agli|agla|kahan|kaha|where|which room|room", t):
        return "next"
    if re.search(r"class|lecture|today|aaj|kal|tomorrow|timetable|schedule|\bkya\b", t):
        return "day"
    return "unknown"


def _target_day(q: str, now: dt.datetime) -> tuple[str, str]:
    t = q.lower()
    if re.search(r"\bkal\b|tomorrow", t):
        d = now + dt.timedelta(days=1)
        return PY_DAY[d.weekday()], "tomorrow"
    if re.search(r"\bparso\b", t):
        return PY_DAY[(now + dt.timedelta(days=2)).weekday()], "day after tomorrow"
    for w, d in DAYWORDS.items():
        if re.search(rf"\b{w}\w*", t):
            return d, d
    return PY_DAY[now.weekday()], "today"


def ask(question: str, user: User, ds, assign: dict, exams: list[dict] | None, applied: list[dict],
        *, group_id: str | None = None, faculty_id: str | None = None, now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or now_ist()
    pt = _period_times(ds.raw["calendar"])
    intent = _intent(question)
    sids, scope = _scope_sessions(user, ds, assign, group_id, faculty_id)
    facts: dict[str, Any] = {"intent": intent, "asked_by_role": user.role, "scope": scope or "none"}
    answer = ""

    if intent == "exam":
        if user.role == "student":
            mine = [e for e in (exams or []) if user.group_id in ds.exams[e["exam_id"]]["groups"]]
        elif scope.startswith("group"):
            g = scope.split()[1]
            mine = [e for e in (exams or []) if g in ds.exams[e["exam_id"]]["groups"]]
        else:
            mine = list(exams or []) if user.role in ("admin", "department_coordinator") else []
        slots = ds.raw["calendar"]["exam_week"]["sessions"]
        st = {s["id"]: f"{s['start']}-{s['end']}" for s in slots}
        order = {d: i for i, d in enumerate(ds.raw["calendar"]["exam_week"]["days"])}
        mine.sort(key=lambda e: (order[e["day"]], e["session"]))
        facts["exams"] = [{"exam": e["exam_id"], "day": e["day"], "time": st[e["session"]], "rooms": e["rooms"]} for e in mine]
        if not exams:
            answer = "The exam timetable has not been generated yet."
        elif not mine:
            answer = "I have no exam entries I can show for you."
        else:
            first = mine[0]
            answer = (f"Your next exam: {first['exam_id'].replace('EX-', '')} on {first['day']} {st[first['session']]} "
                      f"in {', '.join(first['rooms'])}. All {len(mine)} exams: " +
                      "; ".join(f"{e['exam_id'].replace('EX-', '')} {e['day']} {st[e['session']]}" for e in mine) + ". "
                      "(Exam week days are weekday names; the calendar has no dates yet.)")
    elif intent == "teacher":
        m = re.search(r"\b([A-Z]{2,3}\d{3})\b", question.upper())
        cands = [c for c in ds.courses if (m and c == m.group(1))] or \
                [c for c, v in ds.courses.items() if v["title"].lower() in question.lower()]
        if not cands:
            answer = "Tell me the course code (for example CS201) and I'll tell you who teaches it."
        else:
            c = cands[0]
            fs = sorted({ds.faculty[s["faculty_id"]]["name"] for s in ds.sessions.values() if s["course_id"] == c})
            facts["course"], facts["faculty"] = ds.courses[c]["title"], fs
            answer = f"{ds.courses[c]['title']} ({c}) is taught by {', '.join(fs)}." if fs else f"No sessions are scheduled for {c}."
    elif intent == "changes":
        mine = set(sids)
        moved = [m for a in applied for m in a.get("moved", []) if m["session_id"] in mine or user.role in ("admin", "department_coordinator")]
        facts["changes"] = [{"session": m["session_id"], "from": m["from"], "to": m["to"], "reason": m["reason"]} for m in moved]
        if not applied:
            answer = "No timetable changes have been applied yet; your timetable is as originally generated."
        elif not moved:
            answer = "Changes were applied, but none affect your classes."
        else:
            answer = "Your timetable changed: " + "; ".join(
                f"{m['session_id']} moved from {m['from']['day']} P{m['from']['start_period']} {m['from']['room_id']} to "
                f"{m['to']['day']} P{m['to']['start_period']} {m['to']['room_id']} ({m['reason']})" for m in moved) + "."
    elif not sids:
        answer = ("I can answer timetable questions for students and faculty from their own profile. "
                  "As " + user.role.replace("_", " ") + " ask about exams, a course's teacher, or pass a group/faculty to look up.")
    else:
        day, label = _target_day(question, now)
        today = [(sid, assign[sid]) for sid in sids if assign[sid][0] == day]
        today.sort(key=lambda x: x[1][1])
        if intent == "next":
            nowmin = now.hour * 60 + now.minute
            cur_day = PY_DAY[now.weekday()]
            def start_min(e):  # minutes since midnight of the session start
                h, m = pt[e[1][1]][0].split(":")
                return int(h) * 60 + int(m)
            upcoming = None
            for off in range(0, 8):
                d = PY_DAY[(now.weekday() + off) % 7]
                if d not in ds.days:
                    continue
                day_s = sorted(((sid, assign[sid]) for sid in sids if assign[sid][0] == d), key=lambda x: x[1][1])
                if off == 0:
                    day_s = [x for x in day_s if start_min(x) > nowmin]
                if day_s:
                    upcoming = (d, off, day_s[0])
                    break
            if upcoming:
                d, off, (sid, e) = upcoming
                when = "later today" if off == 0 else d
                facts["next"] = {"session": sid, "day": d, "period": e[1], "room": e[2]}
                answer = f"Next class ({when}): {_fmt(ds.sessions[sid], e, ds, pt)}."
            else:
                answer = "I couldn't find an upcoming class."
        elif intent == "free":
            busy = {p for sid, e in today for p in range(e[1], e[1] + ds.sessions[sid]["duration"])}
            free = [p for p in range(1, 10) if p not in busy]
            facts["free_periods"] = free
            if day not in ds.days:
                answer = f"{day} has no teaching periods."
            else:
                rng = ", ".join(f"P{p} ({pt[p][0]})" for p in free) if free else "none"
                answer = f"Free periods {label} ({day}): {rng}."
        else:
            facts["classes"] = [{"session": sid, "day": e[0], "period": e[1], "room": e[2]} for sid, e in today]
            if day not in ds.days:
                answer = f"There are no classes on {day} (teaching week is Monday-Friday)."
            elif not today:
                answer = f"No classes {label} ({day})."
            else:
                answer = f"Classes {label} ({day}): " + "; ".join(_fmt(ds.sessions[sid], e, ds, pt) for sid, e in today) + "."
    result = {"answer": answer, "intent": intent, "facts": facts, "ai_used": False, "ai_error": None,
              "grounded_on": "backend timetable, exam and change records"}
    if intent == "unknown":
        result["answer"] = ("I can help with: your classes today/tomorrow, your next class and room, free periods, exams, "
                            "who teaches a course, and what changed in your timetable. Hinglish works too (e.g. 'Aaj meri next class kaha hai?').")
        return result
    if gemini.configured():
        try:
            text = gemini.generate(
                "You are Campus Buddy for a college. Rewrite the ANSWER for the user in the language of their QUESTION "
                "(English or Hinglish). Use ONLY the information in ANSWER and FACTS. Never add times, rooms, teachers, "
                "exams or changes that are not there. Keep it under 80 words.",
                f"QUESTION: {question}\nANSWER: {result['answer']}\nFACTS: {facts}")
            result["answer"], result["ai_used"] = text.strip(), True
        except gemini.GeminiUnavailable as e:
            result["ai_error"] = f"{e}; showing the deterministic answer"
    else:
        result["ai_error"] = "Gemini not configured; showing the deterministic answer"
    return result
