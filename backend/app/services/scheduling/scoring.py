"""Local mirror of the official soft-penalty formulas (S1-S6).

Used for fast feedback and for reporting solver results independent of auxiliary-variable slack.
The OFFICIAL validator remains the authority; tests assert this mirror agrees with it.
"""
from __future__ import annotations

from collections import defaultdict

from app.services.dataset.loader import LAST_TEACHING, Dataset

Assignment = dict[str, tuple[str, int, str]]


def soft_penalties(ds: Dataset, assign: Assignment) -> dict[str, int]:
    pen: dict[str, int] = defaultdict(int)
    grp_day: dict[tuple, set] = defaultdict(set)
    grp_hours: dict[tuple, int] = defaultdict(int)
    grp_course: dict[tuple, int] = defaultdict(int)
    seen_basket: set = set()
    for sid, (day, start, rid) in assign.items():
        s, r = ds.sessions.get(sid), ds.rooms.get(rid)
        if s is None or r is None:
            continue
        per = ds.periods(start, s["duration"])
        for pref in ds.faculty.get(s["faculty_id"], {}).get("preferences", []):
            if pref.get("type") == "avoid" and day in pref.get("days", ds.days):
                pen["S1"] += 2 * sum(1 for p in per if p in pref["periods"])
        if r["capacity"] and s["size"] / r["capacity"] < 0.4:
            pen["S5"] += 1
        if LAST_TEACHING in per:
            pen["S6"] += 1
        for g in s["groups"]:
            for p in per:
                grp_day[(g, day)].add(p)
            if s.get("basket_slot"):
                if (g, s["basket_slot"]) in seen_basket:
                    continue
                seen_basket.add((g, s["basket_slot"]))
            grp_hours[(g, day)] += s["duration"]
            if s["kind"] == "lecture" and not s.get("basket_slot"):
                grp_course[(g, day, s["course_id"])] += 1
    for ps in grp_day.values():
        pen["S2"] += sum(1 for p in range(min(ps), max(ps) + 1) if p not in ps)
    for h in grp_hours.values():
        if h > 6:
            pen["S3"] += 3 * (h - 6)
    for c in grp_course.values():
        if c > 1:
            pen["S4"] += 3 * (c - 1)
    bc: dict[tuple, int] = defaultdict(int)
    for sid, (day, start, rid) in assign.items():
        s = ds.sessions.get(sid)
        if s and s.get("basket_slot"):
            bc[(s["course_id"], day)] += 1
    for c in bc.values():
        if c > 1:
            pen["S4"] += 3 * (c - 1)
    return {k: int(pen.get(k, 0)) for k in ("S1", "S2", "S3", "S4", "S5", "S6")}
