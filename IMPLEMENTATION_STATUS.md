# Implementation status - OptiCampus (final pass)

## Parser pass (2 Nov 2026) - UNVERIFIED BY TEST RUN
Edited `backend/app/services/ai/faculty_assistant.py`, `frontend/src/pages/Assistant.jsx`, `tests/test_faculty_assistant.py` in a sandbox with **no network**, so pytest/vitest/build/validator were **not run**. Only `py_compile` and a stubbed-import run of `interpret()` on the real dataset were executed.
- Hinglish leave/unavailability ("nahi ho payegi", "leave chahiye", "chutti"), Hindi weekday names, "parso", verb-last moves ("Monday ka lecture Tuesday ko shift karna hai").
- "...leave chahiye, classes reschedule kar do" no longer asks "which class?".
- Fixed a latent crash: a move with a target day but no period (`int(None)`).
- A closed ROOM is no longer misread as the faculty being unavailable.
- Extra-tutorial requests now return `status: not_supported` with an honest message (nothing is created). Elective-basket moves are still refused.
- Needs: `pytest tests/test_faculty_assistant.py` and the full suite, then vitest, on your machine.

Authoritative status. Legend: PASS = implemented and tested here; PARTIAL; FAIL; NOT TESTED. Requirement-by-requirement detail: `docs/REQUIREMENTS_AUDIT.md`.

## Assistant error pass (1 Nov 2026)
- **Reproduced first.** On a fresh backend the sentence "I am unavailable on Wednesday because I have to attend a conference." returns HTTP 200 with validated options for the seeded faculty account, so the *default* path did not fail. Two real defects were found by testing all 40 faculty records x 5 days and by testing accounts:
  1. An account whose `faculty_id` is not in the dataset (typo / different case via Request Access) raised an unhandled `ValueError` -> HTTP 500 "internal server error". Malformed `choices` also gave a 500. **Fixed**: clear 409 (names the bad ID, tells the user to ask an Admin) and 422; regression tests fail on the old code (500) and pass now.
  2. "None of your classes is affected, so nothing needs to move" was returned as a *follow-up question* and shown under "I need a bit more information" (68 of 200 faculty/day combinations). **Fixed**: responses now carry an explicit `status` (`needs_info | nothing_to_move | options | no_solution`); the page renders each correctly and shows a persistent inline error card instead of only a toast.
- Not changed in this pass: rule-based parser coverage for several Hinglish/other phrasings (e.g. "Mujhe Wednesday ko available mat rakhna", "Kal meri faculty meeting hai...", "move my lecture to an earlier period", extra tutorial) still returns a generic follow-up; the UI redesign; booking/exam/dataset items listed above.
- Tests executed: backend `pytest` 153 passed; frontend `vitest` 56 passed (with the real backend running and `VITE_API_BASE_URL=http://localhost:8000`); `npm run build` succeeds.

## Opening experience (latest)
- There is **no landing/marketing page**. The first page is the login page (`/` and `/login`). A glass splash (logo + name only) holds 1 s, pulls down and away (0.7 s), and reveals it. Login layout: very large two-tone serif "OptiCampus" on the left, sign-in card on the right (stacked on phones). Playfair Display is bundled locally. Reduced-motion users get a fade instead of a slide.
- Tested: splash timing with fake timers (shown at 999 ms, leaving at 1 s, removed after 700 ms, scroll restored), login-first, no marketing text, signed-in users skip to the dashboard. **Not seen in a browser**: the glass look and the animation feel are unverified.

## Latest pass (midsem fix, faculty assistant, landing, dark-mode contrast)
- **Midsem bug fixed at the root** (reproduced first): "midsem/midterm" was not an exam keyword; users without a group got a generic "no exam entries" reply; course ("DBMS") and day filters were ignored; no publish step existed. Now: real exam assistant (course names, day, time, duration, venue), publish/withdraw workflow (students see nothing until published, with the specified message), student-group scoping, faculty see exams of courses they teach, explicit explanations for every empty case. The dataset's exam week has weekday names only, so **no calendar dates are shown or invented**; the answer says so.
- **Faculty Schedule Assistant**: leave/unavailability, "move X from A to B", "room unavailable"; candidate search over all hard rules; the whole resulting schedule is re-validated by the **official validator**; alternatives with explanations; conflict report when nothing is valid; submit saves a proposal (server regenerates it; client-sent schedules are ignored); only an Admin can approve/reject; stale proposals (timetable OR data changed) are refused.
- **Dark-mode green contrast**: root cause was a background token used as text colour (dark green on dark green, 1.43:1). Replaced by paired per-theme tone tokens (now 6.98:1) and removed every hard-coded tone colour; guarded by a test.
- Landing page rewritten to the specified copy; glass nav/panels + clay cards; footer statement and copyright; Get Started -> request access, Sign In -> login, Explore Platform -> #features.

## NOT done from the latest brief (explicit)
- Faculty assistant: **extra tutorial / add session** requests and moving **basket (elective)** sessions are not supported; it reports this.
- Campus Buddy does **not** yet answer: room availability ("which room is free tomorrow"), faculty availability, booking status / "why was my booking rejected".
- Booking workflow: approver actions **Request clarification / Suggest alternative room/time** and a **calendar picker** are not built (approve/reject, engine alternatives, accept/decline are).
- Dataset import: no upload **preview**, per-record rejected list or **import history** UI (the API returns counts/errors/warnings; admin JSON import exists). CSV upload is not supported (starter JSON only).
- Exams: admin cannot hand-edit individual exams (regenerate/publish/withdraw only); no invigilator data exists in the dataset.
- Disruptions: side-by-side timetable and "students affected" counts are not built (before/after table with reasons is).
- Dashboards: no day/week/department filters; admin Overview shows real counts but not every metric listed.
- Visual design (glass/clay, dark mode, tablet/phone widths) is **implemented and contrast-checked but never viewed in a browser**.
- Not deployed; PostgreSQL, SMTP and live Gemini untested (unchanged).

## Tests actually executed (this build)
| Suite | Result |
|---|---|
| Backend `pytest` (unit, API, auth, migrations, persistence, scheduler, bookings, exams, disruptions, midsem/Buddy, faculty assistant) | **150 passed** |
| Frontend `vitest` (real React app vs real FastAPI, jsdom) | **56 passed** |
| `npm run build` | succeeds |
| Official validator CLI, `exports/schedule.json` | 0 hard violations, soft 3, booking 67/70, 0 inversions, exam penalty 0 |
| Official validator CLI, `exports/schedule_after.json` (+ disruption + baseline) | 0 hard violations, 12 moved (1 time-slot, 11 room-only), proven minimum |
| `scripts/contrast_check.py` | all 36 token pairs pass WCAG AA in light and dark, including every status tone, button, link and the 12 course colours |

## Fixed in this pass
- **Booking 500** reproduced and fixed at the root (stale migration -> missing columns; non-atomic save; count-based ids; hidden schema drift; muted loggers). Regression tests listed in the audit.
- Real accounts (scrypt), sign-in, request access with Admin approval, forgot/reset (single-use hashed tokens), change password, secure `create_admin.py`; no demo credentials on public pages.
- State (timetable, exams, decisions, applied changes, settings) persisted in the database; survives restart (tested by simulation).
- Disruption repair always solves the full model: lexicographic objective (moves, then time-slot moves, then soft penalty); evidence reported; Admin approve/**reject**; department-targeted notifications.
- Priority order editor, manual scheduling, session explanations, faculty availability assistant, Admin data CRUD + import/export, notification metadata + dedupe.
- UI: OptiCampus branding (wordmark; logo slot), plain-language navigation, role-focused dashboards, FAQ, floating Campus Buddy, stable per-course colours with legend, bundled Inter, auth pages.
- Parser fixed for "2 baje se 4 baje tak" and "computer lab 2".

## NOT done / NOT verified (be aware before submitting)
1. **Logo**: supplied and applied (sidebar, landing, auth pages, favicon, touch icon); the previous generated mark is gone. Covered by a UI test. Not yet *looked at*: how the white badge sits on the dark theme is unverified (see item 2).
2. **No visual inspection**: no browser could be installed, so no page has been looked at in light or dark mode, on a phone or laptop. Layout, spacing, overlap of the floating Buddy with page content, and overall polish are **unverified**. Contrast numbers were computed from the CSS tokens only. Tests run in jsdom, which has no layout engine.
3. **Deployment not done**: Render/Vercel configs are untested; the live site, deployed demo accounts, the live reset button and a PostgreSQL migration run were never checked. Production needs `DATABASE_URL`, `LOCAL_AUTH_SECRET`, `DEMO_PASSWORD`, `CORS_ORIGINS`, `FRONTEND_URL`.
4. **PostgreSQL** never exercised (SQLite only). **SMTP** email never sent (development log path tested). **Gemini** only with mocked responses.
5. **Dataset storage**: the official JSON is loaded at startup; Admin edits persist as a database snapshot (`app_kv`), not as normalised relational tables for rooms/faculty/groups/courses/sessions.
6. Faculty assistant drafts unavailability only (no "extra/moved session" requests); coordinator "request department session changes" not implemented; explanations cover session placement and booking/move reasons, not every "why not" question.
7. Admin Data page edits records as JSON (functional, not user-friendly). Reminder-style notifications (upcoming class/exam) are not generated.
8. Cold single solver run reaches soft ~105; generation warm-starts from the last validated timetable (disclosed). Booking series are decided per request; displacement moves one class at a time.
9. Video walkthrough not produced; `AI_USAGE.md` needs the team to add ChatGPT or any other tool they used.
10. The prompt says P9 ends 17:00; the dataset/validator treat P9 as 17:00-18:00 and were followed.

## Where to continue
Look at every page in both themes and on a phone -> deploy to Render+Vercel with PostgreSQL and run the 5-minute demo on the live site -> record the video.

---
## Earlier history (Parts 1-2 notes, superseded where they conflict with the above)

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
