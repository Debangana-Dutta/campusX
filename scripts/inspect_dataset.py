#!/usr/bin/env python3
"""Inspect the official CIT dataset: counts, enumerations, relationships, integrity.

Read-only. Never modifies source files. Exit code 0 when every check passes.

Usage:
    python scripts/inspect_dataset.py [--data PATH] [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_DATA = (
    Path(__file__).resolve().parents[1]
    / "source_files" / "extracted" / "CrunchWeek_StarterPack" / "data" / "cit_public.json"
)

# Reference counts quoted by the problem statement / starter README.
EXPECTED = {
    "rooms": 27, "faculty": 40, "student_groups": 14, "courses": 62,
    "sessions": 189, "booking_requests": 25, "cancellations": 1, "exams": 41,
}
EXPECTED_TEACHING_HOURS = 243


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--json", help="write findings to this file")
    a = ap.parse_args()

    data = json.loads(Path(a.data).read_text(encoding="utf-8"))
    problems: list[str] = []
    info: dict = {}

    def check(cond: bool, msg: str) -> None:
        if not cond:
            problems.append(msg)

    # ---- counts
    counts = {k: len(data[k]) for k in EXPECTED}
    info["counts"] = counts
    for k, exp in EXPECTED.items():
        check(counts[k] == exp, f"count {k}: expected {exp}, found {counts[k]}")
    hours = sum(s["duration"] for s in data["sessions"])
    info["teaching_hours"] = hours
    check(hours == EXPECTED_TEACHING_HOURS, f"teaching hours: expected {EXPECTED_TEACHING_HOURS}, found {hours}")

    # ---- unique ids
    for key in ("rooms", "faculty", "student_groups", "courses", "sessions", "booking_requests", "exams"):
        ids = [r["id"] for r in data[key]]
        dup = [i for i, c in Counter(ids).items() if c > 1]
        check(not dup, f"duplicate ids in {key}: {dup}")

    rooms = {r["id"]: r for r in data["rooms"]}
    fac = {f["id"]: f for f in data["faculty"]}
    grp = {g["id"]: g for g in data["student_groups"]}
    crs = {c["id"]: c for c in data["courses"]}
    ses = {s["id"]: s for s in data["sessions"]}
    reqs = {b["id"]: b for b in data["booking_requests"]}
    days = set(data["calendar"]["days"])

    # ---- foreign keys
    for s in data["sessions"]:
        check(s["course_id"] in crs, f"{s['id']}: unknown course {s['course_id']}")
        check(s["faculty_id"] in fac, f"{s['id']}: unknown faculty {s['faculty_id']}")
        for g in s["groups"]:
            check(g in grp, f"{s['id']}: unknown group {g}")
        for t in s["room_types"]:
            check(any(r["type"] == t for r in rooms.values()), f"{s['id']}: no room of type {t}")
        fx = s["fixed_slot"]
        if fx:
            check(fx["day"] in days, f"{s['id']}: bad fixed day")
    for u in data["room_unavailability"]:
        check(u["room_id"] in rooms, f"room_unavailability: unknown room {u['room_id']}")
    for f in data["faculty"]:
        for u in f["unavailable"]:
            check(u["day"] in days, f"{f['id']}: bad unavailable day {u['day']}")
    for e in data["exams"]:
        for g in e["groups"]:
            check(g in grp, f"{e['id']}: unknown group {g}")
        for c in e["course_ids"]:
            check(c in crs, f"{e['id']}: unknown course {c}")
    for c in data["cancellations"]:
        check(c["request_id"] in reqs, f"cancellation of unknown request {c['request_id']}")
    for b in data["booking_requests"]:
        check(b["role"] in data["role_category_cap"], f"{b['id']}: unknown role {b['role']}")
        check(b["requested_category"] in data["priority_order"], f"{b['id']}: unknown category")
        if b["requested_room"] is not None and b["requested_room"] not in rooms:
            info.setdefault("requested_rooms_not_in_dataset", []).append((b["id"], b["requested_room"]))
        for g in b["mandatory_for_groups"]:
            check(g in grp, f"{b['id']}: unknown mandatory group {g}")

    # ---- enumerations
    info["enums"] = {
        "room.type": sorted({r["type"] for r in data["rooms"]}),
        "room.allowed_uses": sorted({u for r in data["rooms"] for u in r["allowed_uses"]}),
        "room.features": sorted({x for r in data["rooms"] for x in r["features"]}),
        "session.kind": dict(Counter(s["kind"] for s in data["sessions"])),
        "session.duration": dict(Counter(s["duration"] for s in data["sessions"])),
        "session.basket_slot": dict(Counter(s["basket_slot"] for s in data["sessions"] if s["basket_slot"])),
        "session.needs_accessible": dict(Counter(s["needs_accessible"] for s in data["sessions"])),
        "booking.role": dict(Counter(b["role"] for b in data["booking_requests"])),
        "booking.requested_category": dict(Counter(b["requested_category"] for b in data["booking_requests"])),
        "booking.needs": sorted({n for b in data["booking_requests"] for n in b["needs"]}),
        "faculty.preference.type": sorted({p["type"] for f in data["faculty"] for p in f["preferences"]}),
        "faculty.max_hours_per_day": dict(Counter(f["max_hours_per_day"] for f in data["faculty"])),
    }
    info["fixed_slot_sessions"] = [(s["id"], s["fixed_slot"]) for s in data["sessions"] if s["fixed_slot"]]
    info["accessible_sessions"] = [s["id"] for s in data["sessions"] if s["needs_accessible"]]
    info["faculty_needing_accessible"] = [f["id"] for f in data["faculty"] if f["needs_accessible"]]
    info["groups_needing_accessible"] = [g["id"] for g in data["student_groups"] if g["needs_accessible"]]
    info["room_unavailability"] = data["room_unavailability"]

    # ---- relational sanity
    # sessions whose size disagrees with the sum of their (non-basket) groups
    size_mismatch = []
    for s in data["sessions"]:
        if s["basket_slot"]:
            continue
        gsum = sum(grp[g]["size"] for g in s["groups"] if g in grp)
        if s["size"] != gsum and s["kind"] == "lecture":
            size_mismatch.append((s["id"], s["size"], gsum))
    info["lecture_size_vs_group_sum_mismatch"] = size_mismatch

    # per-faculty weekly load vs availability (quick infeasibility smell test)
    load = defaultdict(int)
    for s in data["sessions"]:
        load[s["faculty_id"]] += s["duration"]
    info["faculty_load_max"] = sorted(load.items(), key=lambda kv: -kv[1])[:5]
    grp_load = defaultdict(int)
    for s in data["sessions"]:
        seen = set()
        for g in s["groups"]:
            key = (g, s["basket_slot"]) if s["basket_slot"] else (g, s["id"])
            if key in seen:
                continue
            seen.add(key)
    # groups' weekly hours (basket counted once per slot)
    gh = defaultdict(float)
    basket_seen = set()
    for s in data["sessions"]:
        for g in s["groups"]:
            if s["basket_slot"]:
                if (g, s["basket_slot"]) in basket_seen:
                    continue
                basket_seen.add((g, s["basket_slot"]))
            gh[g] += s["duration"]
    info["group_weekly_hours"] = dict(sorted(gh.items()))

    info["problems"] = problems
    print(json.dumps(info, indent=2, default=str))
    if a.json:
        Path(a.json).write_text(json.dumps(info, indent=2, default=str), encoding="utf-8")
    print("\nRESULT:", "OK - all checks passed" if not problems else f"{len(problems)} PROBLEM(S)")
    for p in problems:
        print("  -", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
