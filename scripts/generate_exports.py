#!/usr/bin/env python3
"""Generate exports/schedule.json and exports/schedule_after.json with the app's own engines.

Gate: a file is written to exports/ ONLY if the official validator.py accepts it (0 hard violations).
Nothing is hand-edited; every value comes from the solvers/engines.

    python scripts/generate_exports.py timetable --time 240      # (re)optimise, warm-started from last best
    python scripts/generate_exports.py export                    # exams + bookings + disruption, validate, write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings                                   # noqa: E402
from app.services.bookings.engine import BookingEngine                # noqa: E402
from app.services.dataset.loader import load_dataset, load_raw        # noqa: E402
from app.services.exams.scheduler import schedule_exams               # noqa: E402
from app.services.pipeline import apply_change_and_export, assemble_schedule  # noqa: E402
from app.services.scheduling.scoring import soft_penalties            # noqa: E402
from app.services.scheduling.solver import from_schedule, solve_timetable, to_schedule_sessions  # noqa: E402
from app.services.validation.runner import run_validator              # noqa: E402

st = get_settings()
SEED_FILE = st.state_dir / "timetable_seed.json"


def cmd_timetable(a) -> int:
    ds = load_dataset(st.dataset_path)
    hint = None
    prev_total = None
    if SEED_FILE.exists() and not a.fresh:
        prev = json.loads(SEED_FILE.read_text())
        hint = from_schedule({"sessions": prev["sessions"]})
        prev_total = sum(soft_penalties(ds, hint).values())
        print(f"warm start from saved timetable (soft penalty {prev_total})")
    res = solve_timetable(ds, seed=a.seed, time_limit_s=a.time, workers=st.solver_workers, hint=hint,
                          feasibility_share=0.1 if hint else 0.4)
    print(f"solver status: {res.status} | wall {res.wall_time_s:.0f}s | objective {res.objective} | bound {res.best_bound}")
    if not res.has_solution:
        print("NO SOLUTION:", json.dumps(res.diagnosis, indent=2)[:1500])
        return 1
    sched = {"team": st.team_name, "dataset_id": ds.raw["dataset_id"], "sessions": to_schedule_sessions(res.assignment)}
    v = run_validator(sched)
    hard_h = {k: n for k, n in v.report.get("hard_by_rule", {}).items() if k.startswith("H")}
    total = v.report.get("soft_total")
    print(f"official validator: timetable hard violations {hard_h or 0} | soft {v.report.get('soft_penalties')} total {total}")
    if hard_h:
        print("REFUSING to save: hard violations present")
        return 1
    if prev_total is not None and total >= prev_total:
        print(f"no improvement over saved timetable ({prev_total}); keeping the saved one")
        return 0
    st.state_dir.mkdir(parents=True, exist_ok=True)
    SEED_FILE.write_text(json.dumps({"status": res.status, "sessions": sched["sessions"], "soft": res.soft_model,
                                     "soft_total": total, "stats": res.stats}))
    print(f"saved improved timetable (soft {total})")
    return 0


def cmd_export(a) -> int:
    ds = load_dataset(st.dataset_path)
    raw = ds.raw
    seed = json.loads(SEED_FILE.read_text())
    base = from_schedule({"sessions": seed["sessions"]})
    ex = schedule_exams(ds, seed=a.seed, time_limit_s=a.exam_time)
    if not ex.has_solution:
        print("exam scheduling failed:", ex.status, ex.diagnosis); return 1
    outcome = BookingEngine(ds, base).decide()
    sched = assemble_schedule(st.team_name, raw["dataset_id"], base, outcome, ex.exams)
    v = run_validator(sched)
    s = v.summary()
    print(f"schedule.json  -> official: accepted={s['accepted']} hard={s['hard_violation_count']} soft={s['soft_total']} "
          f"booking={s['booking']['booking_score']}/{s['booking']['booking_score_max_if_all_approved']} "
          f"inversions={len(s['priority_inversions'])} exam_soft={s.get('exam_soft_penalty')}")
    if not s["accepted"]:
        print("REFUSING to export schedule.json:", s["hard_violations"][:5]); return 1
    res = apply_change_and_export(raw, json.loads(st.sample_disruption_path.read_text()), sched,
                                  team=st.team_name, seed=a.seed, time_limit_s=a.repair_time)
    if not res["repair"].ok:
        print("repair failed:", res["repair"].status, res["repair"].conflict); return 1
    after = res["schedule_after"]
    va = run_validator(after, disruption_path=st.sample_disruption_path, baseline=sched)
    sa = va.summary()
    print(f"schedule_after -> official: accepted={sa['accepted']} hard={sa['hard_violation_count']} soft={sa['soft_total']} "
          f"stability={sa.get('stability')} booking={sa['booking']['booking_score']} inversions={len(sa['priority_inversions'])}")
    print("minimality:", res["repair"].minimality)
    if not sa["accepted"]:
        print("REFUSING to export schedule_after.json:", sa["hard_violations"][:5]); return 1
    st.exports_dir.mkdir(parents=True, exist_ok=True)
    (st.exports_dir / "schedule.json").write_text(json.dumps(sched, indent=2))
    (st.exports_dir / "schedule_after.json").write_text(json.dumps(after, indent=2))
    print("wrote exports/schedule.json and exports/schedule_after.json (both officially accepted)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("timetable"); t.add_argument("--time", type=int, default=240)
    t.add_argument("--seed", type=int, default=st.solver_seed); t.add_argument("--fresh", action="store_true")
    e = sub.add_parser("export"); e.add_argument("--seed", type=int, default=st.solver_seed)
    e.add_argument("--exam-time", type=int, default=30); e.add_argument("--repair-time", type=int, default=120)
    a = ap.parse_args()
    sys.exit(cmd_timetable(a) if a.cmd == "timetable" else cmd_export(a))
