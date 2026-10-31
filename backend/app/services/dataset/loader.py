"""Load the official CIT dataset and verify its integrity.

The dataset dict is the source of truth. Nothing here fabricates records; an import that
fails integrity checks is reported, never silently repaired.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Counts quoted by the problem statement. Used for *reporting* only.
REFERENCE_COUNTS = {
    "rooms": 27, "faculty": 40, "student_groups": 14, "courses": 62,
    "sessions": 189, "booking_requests": 25, "cancellations": 1, "exams": 41,
}
REFERENCE_TEACHING_HOURS = 243

KIND_TO_USE = {"lecture": "lecture", "tutorial": "tutorial", "lab": "lab"}
LAST_TEACHING = 9
MAX_PERIOD = 13


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass
class Dataset:
    """Indexed, read-only view over the raw dataset dict."""
    raw: dict[str, Any]
    rooms: dict[str, dict] = field(init=False)
    faculty: dict[str, dict] = field(init=False)
    groups: dict[str, dict] = field(init=False)
    courses: dict[str, dict] = field(init=False)
    sessions: dict[str, dict] = field(init=False)
    requests: dict[str, dict] = field(init=False)
    exams: dict[str, dict] = field(init=False)
    cancelled: set[str] = field(init=False)
    days: list[str] = field(init=False)
    lab_starts: set[int] = field(init=False)
    lunch_after: int = field(init=False)
    fac_unavail: dict[str, set[tuple[str, int]]] = field(init=False)
    room_unavail: dict[str, set[tuple[str, int]]] = field(init=False)

    def __post_init__(self) -> None:
        d = self.raw
        self.rooms = {r["id"]: r for r in d["rooms"]}
        self.faculty = {f["id"]: f for f in d["faculty"]}
        self.groups = {g["id"]: g for g in d["student_groups"]}
        self.courses = {c["id"]: c for c in d["courses"]}
        self.sessions = {s["id"]: s for s in d["sessions"]}
        self.requests = {b["id"]: b for b in d.get("booking_requests", [])}
        self.exams = {e["id"]: e for e in d.get("exams", [])}
        self.cancelled = {c["request_id"] for c in d.get("cancellations", [])}
        cal = d["calendar"]
        self.days = list(cal["days"])
        self.lab_starts = set(cal["lab_start_periods"])
        self.lunch_after = cal["lunch"]["after_period"]
        self.fac_unavail = {fid: set() for fid in self.faculty}
        for fid, f in self.faculty.items():
            for u in f.get("unavailable", []):
                for p in u["periods"]:
                    self.fac_unavail[fid].add((u["day"], p))
        self.room_unavail = {rid: set() for rid in self.rooms}
        for u in d.get("room_unavailability", []):
            for p in u["periods"]:
                self.room_unavail.setdefault(u["room_id"], set()).add((u["day"], p))

    # ---- time model helpers (semantics verified against validator.py)
    @staticmethod
    def periods(start: int, duration: int) -> list[int]:
        return list(range(start, start + duration))

    def crosses_lunch(self, start: int, duration: int) -> bool:
        per = self.periods(start, duration)
        return per[0] <= self.lunch_after < per[-1]

    def valid_start(self, session: dict, start: int) -> bool:
        dur = session["duration"]
        if start < 1 or start + dur - 1 > LAST_TEACHING:
            return False
        if self.crosses_lunch(start, dur):
            return False
        if session["kind"] == "lab" and start not in self.lab_starts:
            return False
        return True

    # ---- booking category helpers (mirror validator.effective_category / outranks)
    def effective_category(self, req: dict) -> str:
        order = self.raw["priority_order"]
        cap = self.raw["role_category_cap"].get(req["role"], "club_event")
        asked = order.index(req["requested_category"]) if req["requested_category"] in order else len(order) - 1
        return order[max(asked, order.index(cap))]

    def outranks(self, r1: dict, r2: dict) -> bool:
        order = self.raw["priority_order"]
        c1, c2 = order.index(self.effective_category(r1)), order.index(self.effective_category(r2))
        if c1 != c2:
            return c1 < c2
        return r1["submitted_at"] < r2["submitted_at"]

    def room_features(self, room_id: str) -> set[str]:
        r = self.rooms[room_id]
        return set(r["features"]) | ({"accessible"} if r["accessible"] else set())


def load_raw(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_dataset(path: Path) -> Dataset:
    return Dataset(load_raw(path))


def apply_disruption(raw: dict[str, Any], disruption: dict[str, Any]) -> dict[str, Any]:
    """Apply a disruption file to a *copy* of the dataset (same semantics as the official validator).

    Raises ValueError for unknown change types or references to unknown faculty.
    """
    d = copy.deepcopy(raw)
    fac = {f["id"]: f for f in d["faculty"]}
    for ch in disruption.get("changes", []):
        t = ch.get("type")
        if t == "faculty_unavailable":
            if ch["faculty_id"] not in fac:
                raise ValueError(f"faculty_unavailable: unknown faculty {ch['faculty_id']}")
            for day in ch["days"]:
                fac[ch["faculty_id"]].setdefault("unavailable", []).append(
                    {"day": day, "periods": ch["periods"], "reason": ch.get("reason", "")})
        elif t == "room_unavailable":
            if ch["room_id"] not in {r["id"] for r in d["rooms"]}:
                raise ValueError(f"room_unavailable: unknown room {ch['room_id']}")
            for day in ch["days"]:
                d.setdefault("room_unavailability", []).append(
                    {"room_id": ch["room_id"], "day": day, "periods": ch["periods"], "reason": ch.get("reason", "")})
        elif t == "add_faculty":
            d["faculty"].append(ch["faculty"])
            fac[ch["faculty"]["id"]] = ch["faculty"]
        elif t == "add_session":
            if any(s["id"] == ch["session"]["id"] for s in d["sessions"]):
                raise ValueError(f"add_session: id {ch['session']['id']} already exists")
            d["sessions"].append(ch["session"])
        elif t == "remove_session":
            if not any(s["id"] == ch["session_id"] for s in d["sessions"]):
                raise ValueError(f"remove_session: unknown session {ch['session_id']}")
            d["sessions"] = [s for s in d["sessions"] if s["id"] != ch["session_id"]]
        else:
            raise ValueError(f"Unknown change type: {t}")
    return d


@dataclass
class IntegrityReport:
    ok: bool
    counts: dict[str, int]
    teaching_hours: int
    count_mismatches: list[str]
    errors: list[str]
    warnings: list[str]

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def check_integrity(raw: dict[str, Any]) -> IntegrityReport:
    """Unique ids, foreign keys, malformed/missing fields, count verification."""
    errors: list[str] = []
    dups: list[str] = []
    warnings: list[str] = []
    required = {
        "rooms": ["id", "type", "capacity", "features", "accessible", "allowed_uses"],
        "faculty": ["id", "max_hours_per_day", "unavailable", "preferences"],
        "student_groups": ["id", "size"],
        "courses": ["id"],
        "sessions": ["id", "course_id", "kind", "groups", "faculty_id", "size", "duration",
                     "room_types", "needs_accessible", "basket_slot", "fixed_slot"],
        "booking_requests": ["id", "submitted_at", "role", "requested_category", "attendance",
                             "duration_periods", "windows", "room_types", "needs",
                             "mandatory_for_groups"],
        "exams": ["id", "groups", "size", "duration_hours"],
    }
    for top in ("calendar", "priority_order", "role_category_cap", *required):
        if top not in raw:
            errors.append(f"missing top-level key: {top}")
    if errors:
        return IntegrityReport(False, {}, 0, [], errors, warnings)

    for key, fields in required.items():
        seen: Counter = Counter()
        for i, rec in enumerate(raw[key]):
            if not isinstance(rec, dict):
                errors.append(f"{key}[{i}] is not an object")
                continue
            for f in fields:
                if f not in rec:
                    errors.append(f"{key}[{i}] ({rec.get('id', '?')}): missing field '{f}'")
            seen[rec.get("id")] += 1
        for k, c in seen.items():
            if c > 1:
                dups.append(f"duplicate id in {key}: {k}")
    if errors:  # structural problems (missing fields); relational checks would just crash
        return IntegrityReport(False, {}, 0, [], errors + dups, warnings)
    errors.extend(dups)  # duplicates are reported, and relational checks still run

    ds = Dataset(raw)
    days = set(ds.days)
    for s in raw["sessions"]:
        if s["course_id"] not in ds.courses:
            errors.append(f"{s['id']}: unknown course {s['course_id']}")
        if s["faculty_id"] not in ds.faculty:
            errors.append(f"{s['id']}: unknown faculty {s['faculty_id']}")
        for g in s["groups"]:
            if g not in ds.groups:
                errors.append(f"{s['id']}: unknown group {g}")
        if s["kind"] not in KIND_TO_USE:
            errors.append(f"{s['id']}: unknown kind {s['kind']}")
        if not isinstance(s["duration"], int) or s["duration"] < 1:
            errors.append(f"{s['id']}: bad duration {s['duration']}")
        if not any(r["type"] in s["room_types"] for r in raw["rooms"]):
            errors.append(f"{s['id']}: no room of any required type {s['room_types']}")
        fx = s["fixed_slot"]
        if fx and (fx.get("day") not in days or not isinstance(fx.get("start_period"), int)):
            errors.append(f"{s['id']}: malformed fixed_slot {fx}")
    for u in raw["room_unavailability"]:
        if u["room_id"] not in ds.rooms:
            errors.append(f"room_unavailability: unknown room {u['room_id']}")
    for e in raw["exams"]:
        for g in e["groups"]:
            if g not in ds.groups:
                errors.append(f"{e['id']}: unknown group {g}")
    for c in raw.get("cancellations", []):
        if c["request_id"] not in ds.requests:
            errors.append(f"cancellation for unknown request {c['request_id']}")
    for b in raw["booking_requests"]:
        if b["role"] not in raw["role_category_cap"]:
            errors.append(f"{b['id']}: unknown role {b['role']}")
        if b["requested_category"] not in raw["priority_order"]:
            errors.append(f"{b['id']}: unknown category {b['requested_category']}")
        for g in b["mandatory_for_groups"]:
            if g not in ds.groups:
                errors.append(f"{b['id']}: unknown mandatory group {g}")
        if b.get("requested_room") and b["requested_room"] not in ds.rooms:
            warnings.append(f"{b['id']}: requested room '{b['requested_room']}' does not exist (treated as a wish)")
        for w in b["windows"]:
            if w["to_period"] > MAX_PERIOD:
                warnings.append(f"{b['id']}: window {w['day']} P{w['from_period']}-P{w['to_period']} runs past P{MAX_PERIOD}")

    counts = {k: len(raw.get(k, [])) for k in REFERENCE_COUNTS}
    hours = sum(s["duration"] for s in raw["sessions"])
    mism = [f"{k}: reference {REFERENCE_COUNTS[k]}, actual {counts[k]}"
            for k in REFERENCE_COUNTS if counts[k] != REFERENCE_COUNTS[k]]
    if hours != REFERENCE_TEACHING_HOURS:
        mism.append(f"teaching_hours: reference {REFERENCE_TEACHING_HOURS}, actual {hours}")
    # Count mismatch is informational (a judge's dataset may differ); it is not an integrity error.
    return IntegrityReport(not errors, counts, hours, mism, errors, warnings)
