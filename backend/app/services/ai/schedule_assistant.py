"""Faculty schedule-request assistant: turns a sentence into a DRAFT availability change. It only drafts; the draft goes
through the normal backend repair + official validation, and only an Admin can apply anything."""
from __future__ import annotations

import re
from typing import Any

from app.services.ai.booking_parser import WEEKDAYS

DAYS = ["MON", "TUE", "WED", "THU", "FRI"]


def draft_unavailability(text: str, faculty_id: str) -> dict[str, Any]:
    t = text.lower()
    days = [d for w, d in WEEKDAYS.items() if re.search(rf"\b{w}\b", t) and d in DAYS]
    days = list(dict.fromkeys(days))
    if re.search(r"every day|all week|whole week", t):
        days = DAYS[:]
    periods: list[int] = []
    follow: list[str] = []
    if re.search(r"morning|subah", t):
        periods = [1, 2, 3, 4, 5]
    elif re.search(r"afternoon|after lunch|dopahar", t):
        periods = [6, 7, 8, 9]
    elif re.search(r"all day|whole day|full day|din bhar", t):
        periods = list(range(1, 10))
    else:
        m = re.search(r"p(\d)\s*(?:-|to)\s*p?(\d)", t)
        if m and 1 <= int(m.group(1)) <= int(m.group(2)) <= 9:
            periods = list(range(int(m.group(1)), int(m.group(2)) + 1))
    if not days:
        follow.append("Which day(s) are you unavailable?")
    if not periods:
        follow.append("Which part of the day (morning, afternoon, all day, or periods like P2-P4)?")
    change = None
    if days and periods:
        change = {"type": "faculty_unavailable", "faculty_id": faculty_id, "days": days, "periods": periods,
                  "reason": text.strip()[:120]}
    return {"draft": change, "follow_up": follow, "source": "rules",
            "note": "This is only a draft. Previewing it runs the real repair and validation; nothing changes until an Admin approves."}
