"""Natural-language (English/Hinglish) -> structured booking fields.

The parser only EXTRACTS. It never approves, rejects, ranks or overrides anything: its output is shown to the user
for editing and then goes through the same Pydantic schema and deterministic engine as the manual form.
Gemini is optional; if it is missing or returns invalid data the rule-based parser is used.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

from app.schemas.api import DAYS, FEATURES, ROOM_TYPES
from app.services.ai import gemini

WEEKDAYS = {"mon": "MON", "monday": "MON", "tue": "TUE", "tues": "TUE", "tuesday": "TUE", "wed": "WED", "wednesday": "WED",
            "thu": "THU", "thur": "THU", "thurs": "THU", "thursday": "THU", "fri": "FRI", "friday": "FRI",
            "sat": "SAT", "saturday": "SAT", "sun": "SUN", "sunday": "SUN"}
PY_DAY = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
DEPT = {"computer": "CSE", "cse": "CSE", "mechanical": "ME", "mech": "ME", "civil": "CE", "electrical": "EE",
        "electronics": "ECE", "ece": "ECE", "ee": "EE", "me": "ME", "ce": "CE"}
YEAR = {"first": 1, "second": 2, "third": 3, "1st": 1, "2nd": 2, "3rd": 3}


def hour_to_period(h: int) -> int | None:
    if 8 <= h <= 12:
        return h - 7
    if 14 <= h <= 21:
        return h - 8 if h >= 14 else None
    return None


def _h24(h: int, ap: str | None) -> int:
    if ap == "pm" and h < 12:
        return h + 12
    if ap == "am" and h == 12:
        return 0
    if ap is None and 1 <= h <= 7:
        return h + 12            # campus events at "6" mean evening
    return h


def parse_rules(text: str, today: dt.date | None = None) -> dict[str, Any]:
    t = text.lower()
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    f: dict[str, Any] = {}
    follow: list[str] = []
    assume: list[str] = []
    warn: list[str] = []

    # ---- days
    days: list[str] = []
    for w, d in WEEKDAYS.items():
        if re.search(rf"\b{w}\b", t) and d not in days:
            days.append(d)
    if re.search(r"\bkal\b|\btomorrow\b", t) and not days:
        days.append(PY_DAY[(today.weekday() + 1) % 7])
        assume.append(f"'kal'/'tomorrow' read as tomorrow = {days[0]} (today is {PY_DAY[today.weekday()]})")
    if re.search(r"\baaj\b|\btoday\b", t) and not days:
        days.append(PY_DAY[today.weekday()])
    if re.search(r"\bparso\b", t) and not days:
        days.append(PY_DAY[(today.weekday() + 2) % 7])
    bad = [d for d in days if d not in DAYS]
    if bad:
        warn.append(f"{', '.join(bad)} is outside the Mon-Fri campus week.")
        days = [d for d in days if d in DAYS]

    # ---- times -> periods
    start_p = end_p = None
    m = re.search(r"(\d{1,2})(?::\d\d)?\s*(am|pm|baje)?\s*(?:to|-|se|till|until)\s*(\d{1,2})(?::\d\d)?\s*(am|pm|baje)?", t)
    if m:
        a, ap1, b, ap2 = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
        ap1 = ap1 if ap1 in ("am", "pm") else None          # "baje" means o'clock, not am/pm
        ap2 = ap2 if ap2 in ("am", "pm") else None
        ap1 = ap1 or ap2 if (ap2 and ap1 is None and _h24(a, ap2) < _h24(b, ap2)) else ap1
        h1, h2 = _h24(a, ap1), _h24(b, ap2 or ap1)
        start_p, end_p = hour_to_period(h1), hour_to_period(h2 - 1)
        if ap1 is None and ap2 is None:
            assume.append(f"no am/pm given: read {a}-{b} as {h1}:00-{h2}:00")
    else:
        m = re.search(r"(?:at\s+)?(\d{1,2})(?::\d\d)?\s*(am|pm|baje)\b", t)
        if m:
            h = _h24(int(m.group(1)), m.group(2) if m.group(2) in ("am", "pm") else None)
            start_p = hour_to_period(h)
        elif "after lunch" in t or "afternoon" in t:
            start_p, end_p = 6, 9
            assume.append("'after lunch/afternoon' read as P6-P9 (14:00-18:00); please confirm")
        elif "evening" in t or "shaam" in t:
            start_p, end_p = 10, 13
            assume.append("'evening' read as P10-P13 (18:00-22:00); please confirm")
    if start_p is None:
        follow.append("What time should it start (for example 6 pm)?")

    # ---- duration
    dur = None
    m = re.search(r"(\d+)\s*[- ]?\s*(?:hours?|hrs?|hr|ghante|ghanta|periods?)", t)
    if m:
        dur = int(m.group(1))
    elif start_p and end_p and m is None and re.search(r"(?:to|-|se|till)", t):
        dur = end_p - start_p + 1
        assume.append(f"duration taken from the time range = {dur} period(s)")
    if dur is None:
        follow.append("How long will it run (in hours)?")
    if start_p and dur and not end_p:
        end_p = start_p + dur - 1
    if start_p and end_p and dur and (end_p - start_p + 1) < dur:
        end_p = start_p + dur - 1

    # ---- attendance
    m = re.search(r"(\d[\d,]*)\s*(?:\+\s*)?(?:people|log|participants|students|persons|attendees|members|guests)", t) \
        or re.search(r"(?:around|about|approx\w*|maybe|for)\s+(\d[\d,]*)", t)
    att = int(m.group(1).replace(",", "")) if m else None
    if att is None:
        follow.append("About how many people will attend?")

    # ---- needs
    needs: list[str] = []
    for words, need in (("projector", "projector"), (("mic", "microphone", "pa system", "sound system", "speakers"), "pa_system"),
                        ("stage", "stage"), (("computer", "coding", "laptops"), "computers"),
                        (("wheelchair", "accessible", "accessibility"), "accessible")):
        ws = (words,) if isinstance(words, str) else words
        if any(re.search(rf"\b{w}", t) for w in ws) and need not in needs:
            needs.append(need)

    # ---- room types / named room
    rt: list[str] = []
    if re.search(r"auditorium", t):
        rt = ["auditorium"]
    elif re.search(r"open[- ]air|theatre|theater|\boat\b|outdoor", t):
        rt = ["outdoor"]
    elif re.search(r"seminar", t):
        rt = ["seminar_hall"]
    elif re.search(r"\blab\b", t):
        rt = ["lab_cs"] if "computers" in needs else ["lab_cs", "lab_elec", "lab_phy"]
    elif re.search(r"lecture hall", t):
        rt = ["lecture_hall"]
    elif re.search(r"class ?room", t):
        rt = ["classroom"]
    elif re.search(r"\broom\b|\bvenue\b|\bhall\b|somewhere|kamra|jagah", t):
        rt = ["classroom", "lecture_hall", "seminar_hall"]
    room = None
    m = re.search(r"\b(AUD|OAT|SH-\d|LH-\d|CR-\d{3}|CS-LAB-\d|ELEC-LAB-\d|PHY-LAB|MECH-WS|CIVIL-LAB)\b", text.upper())
    if m:
        room = m.group(1)
    else:
        m = re.search(r"\b(?:computer|cs)\s+lab\s*-?\s*(\d)\b", t)     # "computer lab 2" -> CS-LAB-2
        if m:
            room = f"CS-LAB-{m.group(1)}"
            rt = ["lab_cs"]
    if not rt and not room:
        follow.append("What kind of venue do you need (classroom, seminar hall, auditorium, lab, open-air theatre)?")

    # ---- mandatory groups
    groups: list[str] = []
    if re.search(r"compulsory|mandatory|must attend|zaroori", t):
        for m in re.finditer(r"\b(cse|ece|ee|me|ce)[- ]?([123])\b", t):
            groups.append(f"{m.group(1).upper()}-{m.group(2)}")
        for name, code in DEPT.items():
            if re.search(rf"\b{name}\w*\s+(first|second|third|1st|2nd|3rd)\s+year", t):
                y = YEAR[re.search(rf"\b{name}\w*\s+(first|second|third|1st|2nd|3rd)", t).group(1)]
                if y > 1:
                    groups.append(f"{code}-{y}")
        if not groups:
            follow.append("Which student group(s) must attend? (e.g. CSE-3)")

    cat = "club_event"
    if re.search(r"guest|speaker|industry", t):
        cat = "guest_lecture"
    if re.search(r"department|dept|farewell", t):
        cat = "department_event"
    if re.search(r"inaugur|convocation|spectra", t):
        cat = "institute_event"

    if days and start_p and end_p:
        f["windows"] = [{"day": d, "from_period": start_p, "to_period": end_p} for d in days]
        if len(days) > 1:
            assume.append("several days listed: the booking is for ONE of them; submit separate requests for a series")
    elif days:
        if start_p:
            assume.append(f"start read as P{start_p}; set the end once the duration is known")
    else:
        follow.insert(0, "Which day of the Mon-Fri week is this for?")
    if att:
        f["attendance"] = att
    if dur:
        f["duration_periods"] = dur
    if rt:
        f["room_types"] = rt
    f.update(needs=needs, requested_room=room, mandatory_for_groups=sorted(set(groups)),
             requested_category=cat, title=_title(text), raw_text=text)
    return {"fields": f, "follow_up": sorted(set(follow), key=follow.index), "assumptions": assume, "warnings": warn,
            "source": "rules"}


def _title(text: str) -> str:
    s = re.sub(r"\s+", " ", text.strip())
    return (s[:57] + "...") if len(s) > 60 else (s if len(s) >= 3 else "Venue request")


SYSTEM = ("You extract venue-booking details from a campus request written in English or Hinglish. Output ONLY JSON with "
          "keys: title, attendance(int), duration_periods(int), windows[{day MON-FRI, from_period 1-13, to_period 1-13}], "
          "room_types[from: " + ",".join(ROOM_TYPES) + "], needs[from: " + ",".join(FEATURES) + "], requested_room(string|null), "
          "mandatory_for_groups[string], follow_up[string]. Periods: P1=08:00 ... P5=12:00, lunch 13-14, P6=14:00 ... P9=17:00, "
          "P10=18:00 ... P13=21:00. Use null/omit for anything not stated and add a follow_up question. Never decide approval.")


def _clean_ai(d: dict[str, Any]) -> dict[str, Any] | None:
    try:
        out: dict[str, Any] = {}
        if "attendance" in d and d["attendance"] is not None:
            out["attendance"] = int(d["attendance"])
        if "duration_periods" in d and d["duration_periods"] is not None:
            out["duration_periods"] = int(d["duration_periods"])
        if d.get("windows"):
            ws = []
            for w in d["windows"]:
                if w["day"] not in DAYS or not (1 <= int(w["from_period"]) <= int(w["to_period"]) <= 13):
                    return None
                ws.append({"day": w["day"], "from_period": int(w["from_period"]), "to_period": int(w["to_period"])})
            out["windows"] = ws
        if d.get("room_types"):
            if any(x not in ROOM_TYPES for x in d["room_types"]):
                return None
            out["room_types"] = list(d["room_types"])
        out["needs"] = [x for x in d.get("needs", []) if x in FEATURES]
        out["requested_room"] = d.get("requested_room") or None
        out["mandatory_for_groups"] = [str(x) for x in d.get("mandatory_for_groups", [])]
        if d.get("title"):
            out["title"] = str(d["title"])[:160]
        out["follow_up"] = [str(x) for x in d.get("follow_up", [])]
        return out
    except (KeyError, ValueError, TypeError):
        return None


def parse(text: str, today: dt.date | None = None) -> dict[str, Any]:
    base = parse_rules(text, today)
    base["ai_used"], base["ai_error"] = False, None
    if not gemini.configured():
        base["ai_error"] = "Gemini not configured; used the built-in rule-based parser"
        return base
    try:
        raw = gemini.generate(SYSTEM, f"Today is {(today or dt.date.today()).isoformat()} ({PY_DAY[(today or dt.date.today()).weekday()]}).\nRequest: {text}",
                              json_mode=True)
        clean = _clean_ai(json.loads(raw))
        if clean is None:
            base["ai_error"] = "Gemini returned invalid structured data; it was discarded and the rule-based parser used"
            return base
        fu = clean.pop("follow_up", [])
        merged = {**base["fields"], **{k: v for k, v in clean.items() if v not in (None, [], "")}}
        merged["raw_text"] = text
        return {**base, "fields": merged, "follow_up": fu or base["follow_up"], "source": "gemini", "ai_used": True}
    except (gemini.GeminiUnavailable, json.JSONDecodeError) as e:
        base["ai_error"] = f"{e}; used the rule-based parser"
        return base
