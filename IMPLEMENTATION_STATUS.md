# Implementation status — Part 2 complete (backend + frontend), NOT deployed

## Completed and verified (executed in this environment)
- Backend (Part 1) unchanged in behaviour; 88 pytest tests pass (71 Part 1 + 17 Part 2 + earlier additions).
- Part 2 backend: student read-only role, notifications from real events (+ per-user read receipts), timetable status workflow
  (draft/validated/approved/invalid; approval impossible without official validator acceptance), alternative accept/decline, events feed,
  venues, analytics, admin summary/users/role assignment (no self-assignment)/audit/demo-reset, Campus Buddy, NL booking parser, Gemini client.
- Frontend: landing, login (demo accounts), role shells, 18 pages, claymorphism design system with dark mode, responsive nav drawer, loading/empty/error states, toasts, confirmation dialogs. `npm run build` succeeds.
- 26 full-stack UI tests (real React app against the real backend) pass: login/logout, role menus and guards, timetable grid/views, validation, exams, NL booking -> decision, rejection reasons, notifications, complete disruption preview/approve/apply, Campus Buddy (EN/Hinglish), dark mode, mobile drawer.
- Official validator on both exports: 0 hard violations (see README table). Exports follow the official format (`fest_week.bookings`, `fest_week.session_overrides`, `exams`).

## Not done / not verified
- **No visual QA**: no browser could be installed (network restriction), so there are no screenshots, no real-device or viewport checks. Responsiveness (drawer, agenda view, scrolling grid) is implemented with CSS breakpoints and tested only for behaviour in jsdom, not for appearance. Claymorphism/dark-mode contrast was not eyeballed.
- **Gemini** paths tested only with mocked responses; not run against the live API (no key/outbound access). **Supabase** (DB + JWT auth) code never run against a real project; Alembic migration verified on SQLite only.
- **Not deployed**; Vercel/Render configs are untested. Render's free tier has 1 slow CPU and ephemeral disk (SQLite/state are lost on restart; the app reloads the validated export).
- Local demo auth ships a default secret/password unless env vars are set (a startup warning is logged).
- Faculty "request extra/moved sessions" is not implemented (unavailability requests are); the Availability page says so. Coordinator "request department session changes" likewise not implemented.
- Upcoming-class/exam *reminder* notifications are not generated (only event-driven notifications are); Campus Buddy answers those on request.
- Timetable generate is synchronous (blocks up to the time limit; UI shows real elapsed time, not progress). Cold single run reaches ~soft 105; generate warm-starts from the last validated timetable (disclosed).
- Disruption preview time limits and solver determinism depend on machine speed.
- shadcn/ui is not used (custom clay components instead); frontend is JavaScript as specified.
- File upload of change files is validated client-side (type/size/shape) and server-side (change types, references, max 200 changes); there is no server-side file upload endpoint.
- Booking series (e.g. SER-DANCE) decided per request; displacement moves one class at a time (no chains).

## Earlier (Part 1) notes

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
  Alembic scaffold + initial migration exist and were verified on SQLite only (not on PostgreSQL); the app still calls `create_all` at startup.
- `generate` is synchronous (up to the time limit). A cold single run reaches ~soft 105; reaching 3 used warm-started
  re-solves. `generate` warm-starts from `backend/var/timetable_seed.json` when present (still re-solved + re-validated).
- Displacement moves one class at a time (no chained moves); if a class has nowhere to go the event gets an alternative.
- Booking series (e.g. SER-DANCE) are decided per request, not all-or-nothing.
- Interactive proposals from user bookings: lab and alternative bookings need human approval; others auto-confirm.
- Exams avoid rooms closed by `room_unavailability` (stricter than the validator, which ignores closures for exams).
- Sessions respect room `allowed_uses` (stricter than the validator).
- Determinism holds for a fixed seed on one machine; time-limited solves may differ on other hardware.
- Not tested: concurrency, large datasets, hidden judge change files beyond the five change types.

## Also added after the first review
- `docs/DATASET.md`, `backend/README.md`, Alembic initial migration, `exam_runs` table; timetable versions and exam runs are recorded on generate and on disruption apply.

## Where Part 2 continues
React/Vite frontend over the existing API; Gemini booking parser/explainer behind `services/` producing the existing
`BookingIn` schema (the manual form must keep working); notifications; demo reset; deployment; README demo section.

## Environment variables
See `.env.example`. Test results: `pytest` -> 71 passed. Dataset path: `source_files/extracted/CrunchWeek_StarterPack/`.
