# Implementation status — end of Part 1 (backend)

## Completed and verified
- Dataset discovery, extraction (ZIP preserved, SHA-256 checked), full inspection, integrity checks, CSV==JSON check.
  Actual counts equal the problem statement (27/40/14/62/189 sessions/243 h/25 bookings/41 exams).
- CP-SAT timetable (H1-H12, H14 hard; S1-S6 objective). Soft penalty 3, status OPTIMAL (objective = bound = 3).
- Exams: 41 scheduled, half capacity, multi-room, no room/group clashes, exam penalty 0.
- Booking engine: priority + role caps + submission tie-break, cancellations, window/type/capacity/needs/closures/mandatory
  groups, alternatives, reasoned rejections, class displacement (moved, never dropped). Score 67/70, 0 inversions.
- Disruption repair: sample change -> 12 moved, all directly invalidated (provable minimum for that baseline).
- Official validator wrapper (subprocess, parses `--json`). Exit code 0 is never treated as acceptance.
- 26 API endpoints; local-dev auth; backend role enforcement; self-approval blocked; audit log; export gate.
- **71 automated tests pass** (dataset, validator mutations, solver units, bookings, exams, disruptions, API).

## Not done / known gaps
- No frontend, no Gemini/natural-language layer, no notifications UI, no deployment, no demo-data reset button (Part 2).
- Supabase PostgreSQL and Supabase Auth are **coded but never run against a real Supabase project** (no credentials).
  Alembic is a dependency only; there is no migration scaffold — tables are created with `create_all`.
- `generate` is synchronous (up to the time limit). A cold single run reaches ~soft 105; reaching 3 used warm-started
  re-solves. `generate` warm-starts from `backend/var/timetable_seed.json` when present (still re-solved + re-validated).
- Displacement moves one class at a time (no chained moves); if a class has nowhere to go the event gets an alternative.
- Booking series (e.g. SER-DANCE) are decided per request, not all-or-nothing.
- Interactive proposals from user bookings: lab and alternative bookings need human approval; others auto-confirm.
- Exams avoid rooms closed by `room_unavailability` (stricter than the validator, which ignores closures for exams).
- Sessions respect room `allowed_uses` (stricter than the validator).
- Determinism holds for a fixed seed on one machine; time-limited solves may differ on other hardware.
- Not tested: concurrency, large datasets, hidden judge change files beyond the five change types.

## Where Part 2 continues
React/Vite frontend over the existing API; Gemini booking parser/explainer behind `services/` producing the existing
`BookingIn` schema (the manual form must keep working); notifications; demo reset; deployment; README demo section.

## Environment variables
See `.env.example`. Test results: `pytest` -> 71 passed. Dataset path: `source_files/extracted/CrunchWeek_StarterPack/`.
