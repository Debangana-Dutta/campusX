"""Deterministic Spectra-week booking engine.

AI never decides here. Given the base timetable and the booking requests, every decision is produced by
explicit rules, is reproducible, and carries a human-readable reason.

Rules (source: README + validator.check_bookings):
  * order: effective category (role cap applied) then earlier `submitted_at`
  * cancelled requests are never approved
  * approved  = placed inside one requested window, room fits type / capacity / needs / "event" use,
                free of sessions, other bookings, room closures and mandatory groups' classes
  * alternative_offered = same checks but outside the requested window (half score)
  * rejected  = no compatible placement exists; the reason names the binding constraint
  * only an effective institute_event may displace a regular session; the session is MOVED (override),
    never dropped, and the move must itself satisfy every hard constraint
"""
from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.services.dataset.loader import MAX_PERIOD, Dataset
from app.services.scheduling.solver import Assignment, build_candidates


# ----------------------------------------------------------------------------- week state
class WeekState:
    """Mutable occupancy view of Week 7 (base timetable + overrides + approved bookings)."""

    def __init__(self, ds: Dataset, base: Assignment):
        self.ds = ds
        self.assign: Assignment = {k: tuple(v) for k, v in base.items()}
        self.room_occ: dict[tuple, set] = defaultdict(set)
        self.fac_occ: dict[tuple, set] = defaultdict(set)
        self.grp_occ: dict[tuple, set] = defaultdict(set)
        self.fac_hours: dict[tuple, int] = defaultdict(int)
        self.mand: dict[tuple, set] = defaultdict(set)   # (group, day, p) -> booking ids needing it free
        for sid in list(self.assign):
            self._add(sid)

    def _add(self, sid: str) -> None:
        d, p, r = self.assign[sid]
        s = self.ds.sessions[sid]
        key = s.get("basket_slot") or sid
        for q in range(p, p + s["duration"]):
            self.room_occ[(r, d, q)].add(sid)
            self.fac_occ[(s["faculty_id"], d, q)].add(sid)
            for g in s["groups"]:
                self.grp_occ[(g, d, q)].add(key)
        self.fac_hours[(s["faculty_id"], d)] += s["duration"]

    def _remove(self, sid: str) -> None:
        d, p, r = self.assign[sid]
        s = self.ds.sessions[sid]
        for q in range(p, p + s["duration"]):
            self.room_occ[(r, d, q)].discard(sid)
            self.fac_occ[(s["faculty_id"], d, q)].discard(sid)
            for g in s["groups"]:
                # basket keys can be shared by sibling sessions; only drop when no sibling remains there
                key = s.get("basket_slot") or sid
                if not s.get("basket_slot"):
                    self.grp_occ[(g, d, q)].discard(key)
        self.fac_hours[(s["faculty_id"], d)] -= s["duration"]

    def move(self, sid: str, new: tuple[str, int, str]) -> None:
        self._remove(sid)
        self.assign[sid] = new
        self._add(sid)

    def snapshot(self):
        return copy.deepcopy((self.assign, self.room_occ, self.fac_occ, self.grp_occ, self.fac_hours, self.mand))

    def restore(self, snap) -> None:
        (self.assign, self.room_occ, self.fac_occ, self.grp_occ, self.fac_hours, self.mand) = copy.deepcopy(snap)
        for name in ("room_occ", "fac_occ", "grp_occ", "mand"):
            setattr(self, name, defaultdict(set, getattr(self, name)))
        self.fac_hours = defaultdict(int, self.fac_hours)

    # -- queries
    def session_fits(self, sid: str, d: str, p: int, r: str) -> str | None:
        """None if session `sid` could sit at (d,p,r) in the current state (ignoring its own present slot)."""
        s = self.ds.sessions[sid]
        per = range(p, p + s["duration"])
        cur = self.assign.get(sid)
        cur_per = set()
        if cur:
            cd, cp, cr = cur
            cur_per = {(cr, cd, q) for q in range(cp, cp + s["duration"])}
        key = s.get("basket_slot") or sid
        for q in per:
            occ = self.room_occ.get((r, d, q), set()) - ({sid} if (r, d, q) in cur_per else set())
            if occ:
                return f"room {r} busy {d} P{q}"
            fo = self.fac_occ.get((s["faculty_id"], d, q), set()) - {sid}
            if fo:
                return f"faculty {s['faculty_id']} busy {d} P{q}"
            for g in s["groups"]:
                others = self.grp_occ.get((g, d, q), set()) - {key}
                if others:
                    return f"group {g} busy {d} P{q}"
                if self.mand.get((g, d, q)):
                    return f"group {g} is mandatory for {sorted(self.mand[(g, d, q)])[0]} at {d} P{q}"
        cur_day_h = 0
        if cur and cur[0] == d:
            cur_day_h = s["duration"]
        mx = self.ds.faculty[s["faculty_id"]].get("max_hours_per_day", 4)
        if self.fac_hours[(s["faculty_id"], d)] - cur_day_h + s["duration"] > mx:
            return f"faculty {s['faculty_id']} daily limit {mx}h on {d}"
        return None

    def reserve_booking(self, bid: str, req: dict, room: str, day: str, a: int, b: int) -> None:
        for q in range(a, b + 1):
            self.room_occ[(room, day, q)].add(bid)
            for g in req["mandatory_for_groups"]:
                self.mand[(g, day, q)].add(bid)


# ----------------------------------------------------------------------------- results
@dataclass
class Decision:
    request_id: str
    status: str                      # approved | rejected | alternative_offered
    reason: str
    effective_category: str
    day: str | None = None
    start_period: int | None = None
    end_period: int | None = None
    room_id: str | None = None
    displaced_sessions: list[str] = field(default_factory=list)
    requires_admin_approval: bool = False
    code: str = ""                   # machine-readable reason family

    def export(self) -> dict[str, Any]:
        out: dict[str, Any] = {"request_id": self.request_id, "status": self.status, "reason": self.reason}
        if self.status != "rejected":
            out.update(day=self.day, start_period=self.start_period, end_period=self.end_period, room_id=self.room_id)
        return out

    def as_dict(self) -> dict[str, Any]:
        return {**self.export(), "effective_category": self.effective_category, "code": self.code,
                "displaced_sessions": self.displaced_sessions,
                "requires_admin_approval": self.requires_admin_approval}


@dataclass
class BookingOutcome:
    decisions: list[Decision]
    session_overrides: list[dict[str, Any]]
    week_assignment: Assignment

    def export(self) -> dict[str, Any]:
        order = {d.request_id: i for i, d in enumerate(self.decisions)}
        return {"bookings": [d.export() for d in sorted(self.decisions, key=lambda x: x.request_id)],
                "session_overrides": self.session_overrides}


# ----------------------------------------------------------------------------- engine
class BookingEngine:
    def __init__(self, ds: Dataset, base: Assignment):
        self.ds = ds
        self.base = {k: tuple(v) for k, v in base.items()}
        self.order_idx = {c: i for i, c in enumerate(ds.raw["priority_order"])}
        self.inst_idx = self.order_idx["institute_event"]

    # -- request/room filters
    def room_problems(self, req: dict, rid: str) -> list[str]:
        r = self.ds.rooms[rid]
        out = []
        if "event" not in r["allowed_uses"]:
            out.append("cannot host events")
        if r["type"] not in req["room_types"]:
            out.append(f"type {r['type']} not requested")
        if r["capacity"] < req["attendance"]:
            out.append(f"seats {r['capacity']} < {req['attendance']}")
        miss = set(req["needs"]) - self.ds.room_features(rid)
        if miss:
            out.append("lacks " + "/".join(sorted(miss)))
        return out

    def compatible_rooms(self, req: dict) -> list[str]:
        ok = [rid for rid in self.ds.rooms if not self.room_problems(req, rid)]
        wish = req.get("requested_room")
        return sorted(ok, key=lambda rid: (rid != wish, self.ds.rooms[rid]["capacity"], rid))

    @staticmethod
    def _blocks(req: dict, windows: list[dict]) -> list[tuple[str, int, int]]:
        dur = req["duration_periods"]
        out = []
        for w in windows:
            for a in range(w["from_period"], w["to_period"] - dur + 2):
                b = a + dur - 1
                if a >= 1 and b <= MAX_PERIOD:
                    out.append((w["day"], a, b))
        return out

    def _slot_blockers(self, st: WeekState, req: dict, room: str, day: str, a: int, b: int) -> dict[str, set]:
        """What stands in the way of booking `room` at day P a-b: {'room_closed','room','groups'}."""
        res: dict[str, set] = {"closed": set(), "occupants": set(), "group_sessions": set()}
        for q in range(a, b + 1):
            if (day, q) in self.ds.room_unavail.get(room, ()):
                res["closed"].add(q)
            res["occupants"] |= st.room_occ.get((room, day, q), set())
            for g in req["mandatory_for_groups"]:
                res["group_sessions"] |= {k for k in st.grp_occ.get((g, day, q), set())}
        return res

    # -- placement search
    def _find_free(self, st: WeekState, req: dict, rooms: list[str], blocks) -> tuple | None:
        for rid in rooms:
            for (day, a, b) in blocks:
                bl = self._slot_blockers(st, req, rid, day, a, b)
                if not (bl["closed"] or bl["occupants"] or bl["group_sessions"]):
                    return rid, day, a, b
        return None

    def _alt_blocks(self, req: dict) -> list[tuple[str, int, int]]:
        dur = req["duration_periods"]
        wdays = [w["day"] for w in req["windows"]]
        centre = req["windows"][0]["from_period"] if req["windows"] else 10
        allb = []
        for day in self.ds.days:
            for a in range(1, MAX_PERIOD - dur + 2):
                allb.append((day, a, a + dur - 1))
        # prefer same day as the request, then close to the requested time, then earlier day
        return sorted(allb, key=lambda t: (t[0] not in wdays, abs(t[1] - centre), self.ds.days.index(t[0]), t[1]))

    # -- displacement (institute events only)
    def _try_displace(self, st: WeekState, req: dict, rooms: list[str], blocks) -> tuple | None:
        best = None
        for rid in rooms:
            for (day, a, b) in blocks:
                bl = self._slot_blockers(st, req, rid, day, a, b)
                if bl["closed"]:
                    continue
                # anything that is not a regular, movable, non-basket, non-fixed session blocks outright
                blockers: set[str] = set()
                ok = True
                for x in bl["occupants"] | bl["group_sessions"]:
                    s = self.ds.sessions.get(x)
                    if s is None or s.get("basket_slot") or s.get("fixed_slot"):
                        ok = False
                        break
                    blockers.add(x)
                if not ok or any(st.mand.get((g, day, q)) for g in req["mandatory_for_groups"] for q in range(a, b + 1)):
                    continue
                cost = len(blockers)
                if cost and (best is None or cost < best[0]):
                    best = (cost, rid, day, a, b, sorted(blockers))
        if not best:
            return None
        cost, rid, day, a, b, blockers = best
        snap = st.snapshot()
        moves: dict[str, tuple] = {}
        st.reserve_booking("__pending__", req, rid, day, a, b)
        cands, _ = build_candidates(self.ds, sessions=blockers)
        for sid in blockers:
            s = self.ds.sessions[sid]
            cur = st.assign[sid]
            placed = None
            # temporarily free the session so its own slot doesn't self-conflict, then search nearest slot
            for (d2, p2, r2) in sorted(cands[sid], key=lambda c: (c[0] != cur[0], abs(c[1] - cur[1]),
                                                                  self.ds.days.index(c[0]), c[1], r2_pref(c[2], cur[2]))):
                if (d2, p2, r2) == tuple(cur):
                    continue
                # the new slot may not collide with the pending booking either
                if r2 == rid and d2 == day and not (p2 + s["duration"] - 1 < a or p2 > b):
                    continue
                if st.session_fits(sid, d2, p2, r2) is None:
                    placed = (d2, p2, r2)
                    break
            if placed is None:
                st.restore(snap)
                return None
            st.move(sid, placed)
            moves[sid] = placed
        # drop the pending marker (real reservation is added by the caller)
        for q in range(a, b + 1):
            st.room_occ[(rid, day, q)].discard("__pending__")
            for g in req["mandatory_for_groups"]:
                st.mand[(g, day, q)].discard("__pending__")
        return rid, day, a, b, moves

    # -- explanations
    def _explain_reject(self, st: WeekState, req: dict, eff: str) -> tuple[str, str]:
        ds = self.ds
        att, dur = req["attendance"], req["duration_periods"]
        rooms_all = list(ds.rooms)
        of_type = [r for r in rooms_all if ds.rooms[r]["type"] in req["room_types"] and "event" in ds.rooms[r]["allowed_uses"]]
        if not of_type:
            return "no_room_type", f"No venue of the requested type(s) {req['room_types']} can host events."
        big = [r for r in of_type if ds.rooms[r]["capacity"] >= att]
        if not big:
            mx = max(of_type, key=lambda r: ds.rooms[r]["capacity"])
            return "capacity", (f"No venue seats {att:,}: the largest of the requested type(s) is "
                                f"{mx} at {ds.rooms[mx]['capacity']:,}.")
        comp = self.compatible_rooms(req)
        if not comp:
            need = sorted(set(req["needs"]))
            return "needs", (f"No {'/'.join(req['room_types'])} seating {att} offers all of {need} "
                             f"(checked {', '.join(big)}).")
        if not self._blocks(req, req["windows"]):
            w = req["windows"][0] if req["windows"] else {}
            return "window", (f"The requested window ({w.get('day')} P{w.get('from_period')}-P{w.get('to_period')}) "
                              f"cannot fit {dur} period(s) before the last event period P{MAX_PERIOD} (22:00).")
        # blocked by others: summarise the holders
        holders: dict[str, int] = defaultdict(int)
        closed = 0
        for rid in comp:
            for (day, a, b) in self._blocks(req, req["windows"]):
                bl = self._slot_blockers(st, req, rid, day, a, b)
                closed += bool(bl["closed"])
                for x in bl["occupants"] | bl["group_sessions"]:
                    holders[x] += 1
        books = sorted((h for h in holders if h in ds.requests), key=lambda h: -holders[h])
        sess = sorted((h for h in holders if h in ds.sessions), key=lambda h: -holders[h])
        parts = []
        if books:
            parts.append("already booked by " + ", ".join(books[:3]) + " (higher priority or earlier)")
        if sess:
            parts.append(f"occupied by timetabled class(es) {', '.join(sess[:3])}"
                         + ("" if eff == "institute_event" else " - only an institute event may displace classes"))
        if closed:
            parts.append("closed for maintenance")
        return "conflict", ("Every compatible venue is unavailable in the requested window: "
                            + "; ".join(parts) + "." if parts else "No compatible slot is free in the requested window.")

    def _wish_note(self, st: WeekState, req: dict, room: str) -> str:
        wish = req.get("requested_room")
        if not wish or wish == room:
            return ""
        if wish not in self.ds.rooms:
            return f" Requested room '{wish}' does not exist on campus; {room} meets every stated need."
        probs = self.room_problems(req, wish)
        if probs:
            return f" Requested {wish} does not meet the request ({'; '.join(probs)}); {room} does."
        return f" Requested {wish} is taken in that window; {room} meets every stated need."

    # -- incremental decision for one new request against confirmed state (never overwrites confirmed bookings)
    def state_with(self, confirmed: list[dict[str, Any]], overrides: list[dict[str, Any]]) -> WeekState:
        st = WeekState(self.ds, self.base)
        for o in overrides:
            if o["session_id"] in st.assign:
                st.move(o["session_id"], (o["day"], o["start_period"], o["room_id"]))
        for c in confirmed:
            req = c["_request"]
            st.reserve_booking(req["id"], req, c["room_id"], c["day"], c["start_period"], c["end_period"])
        return st

    def decide_one(self, st: WeekState, req: dict) -> Decision:
        """Decide a single request given the current (confirmed) state. No displacement of classes here:
        moving a class always goes through the batch/admin path."""
        ds = self.ds
        eff = ds.effective_category(req)
        rooms = self.compatible_rooms(req)
        blocks = self._blocks(req, req["windows"])
        found = self._find_free(st, req, rooms, blocks)
        if found:
            room, day, a, b = found
            reason = f"Approved as {eff.replace('_', ' ')}: {room} {day} P{a}-P{b}."
            if eff != req["requested_category"]:
                reason += f" Requested category '{req['requested_category']}' was capped to '{eff}' by the {req['role']} role limit."
            reason += self._wish_note(st, req, room)
            return Decision(req["id"], "approved", reason, eff, day, a, b, room, code="approved")
        alt = self._find_free(st, req, rooms, self._alt_blocks(req)) if rooms else None
        if alt:
            room, day, a, b = alt
            why = self._explain_reject(st, req, eff)[1].rstrip(".")
            return Decision(req["id"], "alternative_offered",
                            f"Requested slot not available ({why}). Offered {room} {day} P{a}-P{b}, which meets every stated need.",
                            eff, day, a, b, room, code="alternative")
        code, why = self._explain_reject(st, req, eff)
        return Decision(req["id"], "rejected", why, eff, code=code)

    def validate_placement(self, st: WeekState, req: dict, room: str, day: str, a: int, b: int) -> list[str]:
        """Hard-rule check for a manual/human placement. Empty list = allowed."""
        ds = self.ds
        errs: list[str] = []
        if room not in ds.rooms:
            return [f"unknown room {room}"]
        if day not in ds.days or a < 1 or b > MAX_PERIOD or b < a:
            return [f"invalid time {day} P{a}-P{b}"]
        if b - a + 1 != req["duration_periods"]:
            errs.append(f"booked {b - a + 1} periods, request needs {req['duration_periods']}")
        errs += [f"{room} {p}" for p in self.room_problems(req, room)]
        bl = self._slot_blockers(st, req, room, day, a, b)
        if bl["closed"]:
            errs.append(f"{room} is closed {day} P{sorted(bl['closed'])}")
        if bl["occupants"]:
            errs.append(f"{room} already used by {', '.join(sorted(bl['occupants']))}")
        if bl["group_sessions"]:
            errs.append(f"mandatory group(s) have class at that time ({', '.join(sorted(bl['group_sessions']))})")
        return errs

    # -- main
    def decide(self) -> BookingOutcome:
        ds = self.ds
        st = WeekState(ds, self.base)
        reqs = sorted(ds.requests.values(), key=lambda r: (self.order_idx[ds.effective_category(r)], r["submitted_at"], r["id"]))
        decisions: dict[str, Decision] = {}
        overrides: list[dict[str, Any]] = []
        pending_alt: list[dict] = []

        for req in reqs:
            eff = ds.effective_category(req)
            rid_ = req["id"]
            if rid_ in ds.cancelled:
                note = next((c["note"] for c in ds.raw["cancellations"] if c["request_id"] == rid_), "")
                decisions[rid_] = Decision(rid_, "rejected", f"Request was cancelled by the requester ({note}); not scheduled.".replace(" ()", ""),
                                           eff, code="cancelled")
                continue
            rooms = self.compatible_rooms(req)
            blocks = self._blocks(req, req["windows"])
            found = self._find_free(st, req, rooms, blocks)
            displaced: dict[str, tuple] = {}
            if not found and self.order_idx[eff] <= self.inst_idx and rooms and blocks:
                dsp = self._try_displace(st, req, rooms, blocks)
                if dsp:
                    rid_r, day, a, b, displaced = dsp
                    found = (rid_r, day, a, b)
            if found:
                room, day, a, b = found
                st.reserve_booking(rid_, req, room, day, a, b)
                reason = f"Approved as {eff.replace('_', ' ')}: {room} {day} P{a}-P{b}."
                if eff != req["requested_category"]:
                    reason += (f" Requested category '{req['requested_category']}' was capped to '{eff}' "
                               f"by the {req['role']} role limit.")
                reason += self._wish_note(st, req, room)
                dec = Decision(rid_, "approved", reason, eff, day, a, b, room, sorted(displaced),
                               requires_admin_approval=bool(displaced), code="approved")
                if displaced:
                    dec.reason += " Moved class(es): " + ", ".join(
                        f"{s} -> {v[0]} P{v[1]} {v[2]}" for s, v in sorted(displaced.items())) + "."
                    for sid, (d2, p2, r2) in sorted(displaced.items()):
                        overrides.append({"session_id": sid, "day": d2, "start_period": p2, "room_id": r2,
                                          "displaced_by": rid_})
                decisions[rid_] = dec
            else:
                pending_alt.append(req)

        # pass 2: alternatives (never displace; never steal in-window slots from lower-priority requests)
        for req in pending_alt:
            eff = ds.effective_category(req)
            rooms = self.compatible_rooms(req)
            alt = self._find_free(st, req, rooms, self._alt_blocks(req)) if rooms else None
            if alt:
                room, day, a, b = alt
                st.reserve_booking(req["id"], req, room, day, a, b)
                why_no = self._explain_reject(st, req, eff)[1]
                decisions[req["id"]] = Decision(
                    req["id"], "alternative_offered",
                    f"Requested slot not available ({why_no.rstrip('.')}). Offered {room} {day} P{a}-P{b}, which meets every stated need.",
                    eff, day, a, b, room, code="alternative")
            else:
                code, why = self._explain_reject(st, req, eff)
                decisions[req["id"]] = Decision(req["id"], "rejected", why, eff, code=code)

        ordered = [decisions[r["id"]] for r in reqs]
        return BookingOutcome(ordered, overrides, dict(st.assign))


def r2_pref(room: str, cur_room: str) -> int:
    return 0 if room == cur_room else 1
