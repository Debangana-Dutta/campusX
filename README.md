# Campus X — One Campus. Zero Clashes. Smarter Decisions.

Campus scheduling and venue management for Chilika Institute of Technology (Tech Zephyr hackathon, "Crunch Week").
Core principle: **AI interprets and assists; deterministic backend code decides and validates.**

## What it does (all implemented and tested)
- **Timetable**: OR-Tools CP-SAT places all 189 sessions (day, period, room) under every hard constraint; soft penalties mirror the official formulas.
- **Official validation**: the organisers' `validator.py` (unmodified) is run as a separate process; nothing is "approved" or exported unless it reports 0 hard violations.
- **Spectra week bookings**: deterministic priority/role-cap/tie-break engine with a reason for every approval, alternative and rejection; class displacement only for institute events and only by *moving* the class.
- **Exams**: 41 midsems across rooms at half capacity (multi-room), no room/group clashes.
- **Disruptions**: minimum-movement repair, before/after diff, official validation, then **Admin approval** before anything is applied.
- **Natural-language booking** (English/Hinglish): extraction only (Gemini optional, rule-based fallback), review/edit form, deterministic decision. The manual form always works.
- **Campus Buddy**: grounded, role-scoped timetable/exam/change assistant (Hinglish supported); Gemini may only rephrase backend facts.
- **Notifications** from real events, role dashboards (admin, faculty, department coordinator, club representative) and a read-only student view, claymorphism UI with dark mode, responsive layout.

## Verified results
| Item | Result |
|---|---|
| `exports/schedule.json` (official validator CLI) | 0 hard violations, soft penalty 3 (CP-SAT OPTIMAL), booking score 67/70, 0 priority inversions, exam penalty 0 |
| `exports/schedule_after.json` (sample disruption + baseline) | 0 hard violations, 12 sessions moved (4 time, 8 room-only; each directly invalidated by the change) |
| Backend tests | 88 passed (`pytest`) |
| Frontend UI tests (real React app vs real backend) | 26 passed (`npm test`) |
| Production build | `npm run build` succeeds |

Reproduce: `cd source_files/extracted/CrunchWeek_StarterPack && python validator.py --data data/cit_public.json --schedule ../../../exports/schedule.json`

## Architecture
```
 React + Vite + Tailwind (frontend/) ──HTTPS──> FastAPI (backend/app)
   claymorphism UI, role routes                   ├─ api/routes     thin HTTP layer + backend authorisation
                                                  ├─ services/scheduling   CP-SAT model, soft-score mirror
                                                  ├─ services/validation   official validator.py via subprocess
                                                  ├─ services/bookings     deterministic engine, week-state, displacement
                                                  ├─ services/exams        CP-SAT exam allocation
                                                  ├─ services/disruptions  minimum-movement repair
                                                  ├─ services/ai           Gemini client, booking parser, Campus Buddy
                                                  └─ SQLAlchemy ── SQLite (local) / Supabase PostgreSQL
 Original dataset + validator: source_files/ (preserved, never modified)
```
Stack: Python 3.12, FastAPI, Pydantic, SQLAlchemy/Alembic, OR-Tools; React 18, Vite 5, Tailwind 3, React Router, Framer Motion, Recharts, Lucide.

## Project structure
`backend/app/{api,core,models,schemas,services}` · `backend/migrations` · `frontend/src/{pages,components,features,layouts,contexts,services,hooks,utils,routes}` ·
`tests/` (pytest) · `frontend/src/__tests__` (vitest) · `scripts/` (dataset inspection, export generation) · `docs/DATASET.md` · `exports/` · `source_files/` (original ZIP + extracted starter pack)

## Setup (local)
```
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && PYTHONPATH=. uvicorn app.main:app --port 8000          # API + docs at http://localhost:8000/docs
# second terminal
cd frontend && npm ci && npm run dev                                 # http://localhost:5173 (proxies /api to :8000)
```
On first start the backend loads `exports/schedule.json` (the app's own validated export), re-validates it with the official validator, and shows it as the starting timetable. Admin → *Generate Timetable* runs the solver for real; *Settings → Reset demo data* returns to the clean state.

Dataset import: automatic at startup (`POST /api/dataset/import` re-runs integrity checks; `?reset=true` resets derived state). `python scripts/inspect_dataset.py` prints the full inspection report; see `docs/DATASET.md`.

Regenerate exports: `python scripts/generate_exports.py timetable --time 240` (repeat to improve; warm-started) then `python scripts/generate_exports.py export` (writes only if the official validator accepts).

## Demo accounts (LOCAL DEVELOPMENT AUTH — demo mode, not production authentication)
Password for all: `campusx-demo` (override with `DEMO_PASSWORD`).
| Username | Role | Notes |
|---|---|---|
| `admin` | admin (Dean's office) | everything, incl. *Reset demo data* |
| `faculty` | faculty (F01) | own timetable, availability |
| `coordinator` | department_coordinator (CSE) | department view, approves CSE lab bookings |
| `club` | club_representative (Dramatics Society) | venue requests |
| `student` | read-only student (CSE-2) | own group only; **not** an approval role |
Set `AUTH_MODE=supabase` to verify Supabase JWTs instead (role from `app_metadata.role`, which users cannot self-assign).

## Environment variables
See `.env.example` (backend) and `frontend/.env.example` (`VITE_API_BASE_URL`). Only variables actually read by the code are listed.
Secrets (`GEMINI_API_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`) are backend-only and never reach the browser.

## API (all under `/api`)
`health` · `auth/local-login|me` · `dataset/status|summary|import` · `timetable` `[/group|faculty|room/{id}]` `/generate|validate|approve|export` ·
`bookings` `[/parse|/{id}|/{id}/decision|/{id}/respond|/{id}/cancel]` · `exams` `[/generate]` · `disruptions` `[/sample|/preview|/apply|/{id}/comparison]` ·
`notifications` `[/read|/announce]` · `buddy/ask` · `ai/status` · `venues` · `events` · `reports/room-utilisation|analytics|validation` · `admin/summary|users|role-assignments|audit|demo-reset`

## Engines in brief
- **Scheduling**: candidate placements filtered by every per-session rule; exact-one placement, room/faculty/group no-overlap, basket sync, daily limits as constraints; objective = S1–S6 (verified equal to the validator). Reports the real CP-SAT status (OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN) and explains infeasibility.
- **Bookings**: order by effective category (role-capped) then submission time; approved = fully inside one requested window; alternatives may be outside the window (half score); rejections state the binding constraint.
- **Disruptions**: apply the change to a copy → pin unaffected sessions → free affected/added → optional full re-solve with a movement-first objective; "proven minimum" is claimed only when the solver status and the lower bound support it.

## Deployment (prepared, NOT deployed)
- **Backend → Render**: `render.yaml` (health check `/api/health`). Set `CORS_ORIGINS` to the Vercel URL, `DEMO_PASSWORD`, optionally `DATABASE_URL` (Supabase), `GEMINI_API_KEY`.
- **Frontend → Vercel**: root directory `frontend`, env `VITE_API_BASE_URL=https://<render-service>.onrender.com`; `vercel.json` handles SPA routing and security headers.
- **Supabase**: create a project, set `DATABASE_URL`, run `cd backend && alembic upgrade head`.
No deployment has been performed or checked; no credentials were available.

## Known limitations
See `IMPLEMENTATION_STATUS.md` (authoritative). Highlights: no real browser/visual QA was possible in the build sandbox (no screenshots); Gemini and Supabase paths are implemented but untested against the live services; Render's free tier is slow for solver runs and its disk is ephemeral.
