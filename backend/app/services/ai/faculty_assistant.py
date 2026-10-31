"""Faculty scheduling assistant.

Pipeline (the AI/parser never touches the timetable):
  text -> interpret() structured request -> candidate search over the real hard rules (build_candidates + WeekState)
       -> every proposal re-checked by the OFFICIAL validator on the complete resulting schedule
       -> alternatives + explanation  ->  (faculty submits) saved as a PROPOSAL  ->  Admin approves  ->  transaction.
A proposal the validator rejects is never offered. If nothing valid exists, a conflict report says why.
"""
from __future__ import annotations

import copy
import datetime as dt
import re
from collections import Counter
from typing import Any

from app.services.ai import buddy, exam_assistant
from app.services.ai.booking_parser import WEEKDAYS
from app.services.bookings.engine import BookingEngine, WeekState
from app.services.dataset.loader import Dataset, apply_disruption
from app.services.scheduling.scoring import soft_penalties
from app.services.scheduling.solver import Assignment, build_candidates, to_schedule_sessions
from app.services.validation.runner import run_validator_on_dataset

DAYS = ["MON", "TUE", "WED", "THU", "FRI"]
UNAVAIL = r"unavailable|on leave|\bleave\b|can't|cannot|can not|not available|conference|\baway\b|busy|absent|chutti|nahi aa"


def _days_in(t: str, now: dt.datetime) -> list[str]:
    out = [d for w, d in WEEKDAYS.items() if re.search(rf"\b{w}\b", t) and d in DAYS]
    if re.search(r"\btomorrow\b|\bkal\b", t):
        out.append(buddy.PY_DAY[(now.weekday() + 1) % 7])
    if re.search(r"\btoday\b|\baaj\b", t):
        out.append(buddy.PY_DAY[now.weekday()])
    return [d for d in dict.fromkeys(out)]


def interpret(text: str, ds: Dataset, faculty_id: str, assign: Assignment, now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or buddy.now_ist()
    t = text.lower()
    m = re.search(r"\b(move|shift|reschedule|swap|change)\b", t)
    left, right = (t[:m.start()], t[m.start():]) if m else (t, "")
    mine = {sid: s for sid, s in ds.sessions.items() if s["faculty_id"] == faculty_id}
    out: dict[str, Any] = {"unavailable": None, "targets": [], "reason": "", "follow_up": [], "notes": [], "room_problem": False}

    unavailable_days: list[str] = []
    if re.search(UNAVAIL, left):
        unavailable_days = _days_in(left, now)
        non_teaching = [d for d in unavailable_days if d not in DAYS]
        unavailable_days = [d for d in unavailable_days if d in DAYS]
        if not unavailable_days:
            out["follow_up"].append("Which weekday(s) are you unavailable? (The teaching week is Monday to Friday.)")
        else:
            periods = list(range(1, 10))
            if re.search(r"morning|subah", left):
                periods = [1, 2, 3, 4, 5]
            elif re.search(r"afternoon|after lunch|dopahar", left):
                periods = [6, 7, 8, 9]
            else:
                pm = re.search(r"p(\d)\s*(?:-|to)\s*p?(\d)", left)
                if pm and 1 <= int(pm.group(1)) <= int(pm.group(2)) <= 9:
                    periods = list(range(int(pm.group(1)), int(pm.group(2)) + 1))
            out["unavailable"] = {"type": "faculty_unavailable", "faculty_id": faculty_id, "days": unavailable_days, "periods": periods,
                                  "reason": text.strip()[:120]}
    if re.search(r"room.*(unavailable|closed|maintenance|not available)|(unavailable|closed).*room", t):
        out["room_problem"] = True

    # ---- course / kind named in the move clause (or anywhere when only a room problem is reported)
    scope = right or t
    _, course_ids = exam_assistant._named_course(scope, ds, set())
    kind = next((k for k in ("lecture", "tutorial", "lab") if re.search(rf"\b{k}", scope)), None)
    src_day = tgt_day = None
    src_p = tgt_p = None
    mv = re.search(r"from\s+(?:(\w+day|mon|tue|wed|thu|fri)\b)?\s*(?:p(\d))?\s*to\s+(?:(\w+day|mon|tue|wed|thu|fri)\b)?\s*(?:p(\d))?", right)
    if mv:
        src_day, src_p, tgt_day, tgt_p = WEEKDAYS.get(mv.group(1) or "", None), mv.group(2), WEEKDAYS.get(mv.group(3) or "", None), mv.group(4)
    elif right:
        ds_in = [d for w, d in WEEKDAYS.items() if re.search(rf"\b{w}\b", right)]
        src_day = ds_in[0] if ds_in else None
        if re.search(r"\bto\s+(\w+day)\b", right):
            tgt_day = WEEKDAYS.get(re.search(r"\bto\s+(\w+day)\b", right).group(1))
    wanted = []
    if right or out["room_problem"]:
        for sid, s in mine.items():
            if course_ids and s["course_id"] not in course_ids:
                continue
            if kind and s["kind"] != kind:
                continue
            if out["room_problem"] and not right and s["kind"] != "lab" and not course_ids:
                continue
            d, p, _ = assign[sid]
            if src_day and d != src_day:
                continue
            if src_p and p != int(src_p):
                continue
            wanted.append(sid)
        if right and not wanted:
            out["follow_up"].append("I couldn't find a class of yours matching that. Which course, and which day/period is it now?")
        elif len(wanted) > 3 and right:
            out["follow_up"].append(f"That matches {len(wanted)} of your sessions ({', '.join(wanted[:4])}…). Which day and period is the one to move?")
            wanted = []
    out["targets"] = [{"sid": sid, "to": ((tgt_day or assign[sid][0]), int(tgt_p)) if (tgt_p or tgt_day) else None,
                       "target_day": tgt_day, "target_period": int(tgt_p) if tgt_p else None} for sid in wanted]
    if not right and not out["unavailable"] and not out["room_problem"] and not out["follow_up"]:
        out["follow_up"].append("Tell me what to change: when you are unavailable, or which class to move (and to when).")
    return out


_CATS = (("room", re.compile(r"^room \S+ busy")), ("faculty", re.compile(r"^faculty \S+ busy")), ("group", re.compile(r"^group \S+ busy")),
         ("mandatory-group booking", re.compile(r"mandatory")), ("faculty daily limit", re.compile(r"daily limit")))


def _cat(reason: str) -> str:
    return next((n for n, rx in _CATS if rx.search(reason)), "other")


def alternatives(ds: Dataset, st: WeekState, assign: Assignment, sid: str, *, avoid_room: bool = False, target=None, limit: int = 3):
    """Valid alternative slots for one session, plus a tally of why other slots were rejected."""
    s = ds.sessions[sid]
    cur = tuple(assign[sid])
    cands, why = build_candidates(ds, sessions=[sid])
    reasons: Counter = Counter()
    valid: list[tuple] = []
    if s.get("basket_slot"):
        return [], {"constraints": ["elective basket sessions must stay synchronised, so they cannot be moved individually"]}, why[sid]
    for (d, p, r) in cands[sid]:
        if (d, p, r) == cur or (avoid_room and r == cur[2]):
            continue
        if target and (d, p) != target:
            continue
        why_not = st.session_fits(sid, d, p, r)
        if why_not:
            reasons[_cat(why_not)] += 1
        else:
            valid.append((d, p, r))
    di = lambda d: DAYS.index(d)
    valid.sort(key=lambda c: ((c[0], c[1]) != cur[:2], abs(di(c[0]) - di(cur[0])), abs(c[1] - cur[1]), c[2]))
    ranked = []
    for c in valid[:14]:
        tmp = dict(assign); tmp[sid] = c
        ranked.append((c, sum(soft_penalties(ds, tmp).values())))
    ranked.sort(key=lambda x: ((x[0][0], x[0][1]) != cur[:2], x[1], abs(di(x[0][0]) - di(cur[0])), abs(x[0][1] - cur[1])))
    return ranked[:limit], dict(reasons), why[sid]


def _explain(ds: Dataset, sid: str, to, reasons: dict, elim: dict) -> str:
    """Why the explicitly requested slot cannot be used (from the real rules, in order of the checks)."""
    s, (d, p) = ds.sessions[sid], (to[0], to[1])
    if not ds.valid_start(s, p):
        return f"P{p} is not a valid start for a {s['duration']}-hour {s['kind']} (periods run P1-P9, no session may cross lunch, labs start only at P2 or P6)."
    per = ds.periods(p, s["duration"])
    if any((d, q) in ds.fac_unavail[s["faculty_id"]] for q in per):
        return f"{s['faculty_id']} is unavailable on {d} at that time."
    if reasons:
        return f"On {d} P{p} every suitable room fails a hard rule: " + ", ".join(f"{k} ({v} room option(s))" for k, v in reasons.items()) + "."
    return f"No room of type {', '.join(s['room_types'])} with {s['size']}+ seats is open on {d} P{p} (closures, capacity or type)."


def explain_alt(ds: Dataset, sid: str, cur, new, soft_before: int, soft_after: int) -> list[str]:
    s = ds.sessions[sid]
    sizes = sum(ds.groups[g]["size"] for g in s["groups"] if g in ds.groups)
    return [f"{sid} moves from {cur[0]} P{cur[1]} {cur[2]} to {new[0]} P{new[1]} {new[2]} ({'room only, same time' if cur[:2] == tuple(new[:2]) else 'time changes'}).",
            f"Checked: faculty {s['faculty_id']} is free and within the daily limit; groups {', '.join(s['groups'])} are free; room {new[2]} is free, seats {ds.rooms[new[2]]['capacity']} for {s['size']} students and has the right type; no lunch, lab-start or closure rule is broken.",
            f"Affects {len(s['groups'])} group(s) ({sizes} students in those groups). Soft penalty {soft_before} -> {soft_after}."]


def build(ds_live_raw: dict, schedule_now: dict, assign_now: Assignment, exams, confirmed, overrides, faculty_id: str, text: str,
          choices: dict[str, int] | None = None, now=None) -> dict[str, Any]:
    """Interpret -> search -> combine -> official validation. Returns everything the UI needs; changes nothing."""
    ds = Dataset(ds_live_raw)
    it = interpret(text, ds, faculty_id, assign_now, now)
    res: dict[str, Any] = {"interpretation": {k: it[k] for k in ("unavailable", "targets", "room_problem")}, "follow_up": it["follow_up"],
                           "alternatives": {}, "no_solution": [], "proposal": None, "text": text}
    if it["follow_up"] and not (it["unavailable"] or it["targets"]):
        return res
    change = it["unavailable"]
    new_raw = apply_disruption(ds_live_raw, {"changes": [change]}) if change else copy.deepcopy(ds_live_raw)
    nds = Dataset(new_raw)
    eng = BookingEngine(nds, assign_now)
    st = eng.state_with(confirmed, overrides)
    affected: dict[str, dict] = {}
    if change:
        for sid, (d, p, r) in assign_now.items():
            s = nds.sessions[sid]
            if s["faculty_id"] == faculty_id and d in change["days"] and any(q in change["periods"] for q in range(p, p + s["duration"])):
                affected[sid] = {"reason": f"you are unavailable {d} P{change['periods'][0]}-P{change['periods'][-1]}", "to": None}
    for t in it["targets"]:
        affected.setdefault(t["sid"], {"reason": "you asked to move it" if not it["room_problem"] else "its room is unavailable", "to": t["to"]})
        if t["to"]:
            affected[t["sid"]]["to"] = t["to"]
    if not affected:
        res["follow_up"] = res["follow_up"] or ["None of your classes is affected by that, so nothing needs to move."]
        return res

    working = dict(assign_now)
    chosen: dict[str, tuple] = {}
    for sid, info in affected.items():
        alts, reasons, elim = alternatives(nds, st, working, sid, avoid_room=bool(it["room_problem"] and not info["to"]),
                                           target=tuple(info["to"]) if info["to"] else None)
        if not alts and info["to"]:                       # explicit target impossible: say why, then offer other slots
            _, reasons_t, _ = alternatives(nds, st, working, sid, target=tuple(info["to"]))
            alts_any, _, _ = alternatives(nds, st, working, sid)
            res["no_solution"].append({"session_id": sid, "asked": f"{info['to'][0]} P{info['to'][1]}", "reason": info["reason"],
                                       "why_not": _explain(nds, sid, info['to'], reasons_t, elim), "other_options": [
                                           {"day": a[0][0], "start_period": a[0][1], "room_id": a[0][2]} for a in alts_any]})
            alts = alts_any
        if not alts:
            res["no_solution"].append({"session_id": sid, "reason": info["reason"], "affected_sessions": [sid],
                                       "rejected_slots_by_constraint": reasons, "removed_by_hard_rules": elim,
                                       "why_not": "No valid day/period/room remains for this session once every hard rule is applied."})
            continue
        before = sum(soft_penalties(nds, working).values())
        res["alternatives"][sid] = []
        for c, soft in alts:
            res["alternatives"][sid].append({"day": c[0], "start_period": c[1], "room_id": c[2], "soft_penalty_after": soft, "soft_penalty_before": before,
                                             "explanation": explain_alt(nds, sid, working[sid], c, before, soft)})
        pick = (choices or {}).get(sid, 0)
        pick = pick if 0 <= pick < len(alts) else 0
        c = alts[pick][0]
        if st.session_fits(sid, *c) is None:             # sequential re-check: earlier chosen moves change the state
            st.move(sid, c); working[sid] = c; chosen[sid] = c
        else:
            res["no_solution"].append({"session_id": sid, "reason": "earlier chosen moves took the slot", "why_not": "re-run to get fresh options"})
    if res["no_solution"] and not chosen:
        return res
    if not chosen:
        return res

    after_assign = working
    outcome = BookingEngine(nds, after_assign).decide()
    after = {"team": schedule_now.get("team", ""), "dataset_id": schedule_now["dataset_id"], "sessions": to_schedule_sessions(after_assign),
             "fest_week": outcome.export()}
    if exams is not None:
        after["exams"] = exams
    v = run_validator_on_dataset(new_raw, after, baseline=schedule_now)         # INDEPENDENT validation of the whole result
    summ = v.summary()
    moved = [{"session_id": sid, "from": {"day": assign_now[sid][0], "start_period": assign_now[sid][1], "room_id": assign_now[sid][2]},
              "to": {"day": c[0], "start_period": c[1], "room_id": c[2]}, "reason": affected[sid]["reason"],
              "time_changed": tuple(assign_now[sid][:2]) != tuple(c[:2])} for sid, c in chosen.items()]
    res["proposal"] = {"feasible": bool(summ["accepted"]), "validation": summ, "moved": moved, "affected": {k: [v_["reason"]] for k, v_ in affected.items()},
                       "schedule_after": after, "changes": [change] if change else [], "chosen": {k: list(v_) for k, v_ in chosen.items()}}
    if not summ["accepted"]:
        res["proposal"]["rejected_by_validator"] = [x["detail"] for x in summ["hard_violations"][:10]]
    return res
