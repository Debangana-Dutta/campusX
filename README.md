# OptiCampus

Timetables, room booking and exams for campus (built for the CIT "Crunch Week" hackathon).
Backend code makes every scheduling and booking decision; AI only helps read requests and answer questions.

## What it does
- **Timetable**: OR-Tools CP-SAT places all 189 sessions (day, period, room) under every hard constraint and minimises the official soft penalties.
- **Official validator**: the organisers' `validator.py` (unmodified) is run as a separate process. Nothing is approved or exported unless it reports 0 hard violations.
- **Room booking**: request in English or Hinglish, review/edit the parsed form, submit. A deterministic engine applies the official priority order and role caps and records a reason for every decision.
- **Schedule changes**: faculty leave, closed rooms, new sessions. The system proposes the fewest moves with solver evidence, shows exactly what changes, and only an Admin can apply or reject it.
- **Exams**: 41 midsems at half room capacity, multi-room, no clashes.
- **Manual scheduling** (same checks as automatic), **Admin data management** (rooms, faculty, groups, courses, sessions; import/export), **notifications**, **FAQs**, floating **Campus Buddy**.

## Verified results (official validator CLI)
| Item | Result |
|---|---|
| `exports/schedule.json` | 0 hard violations · soft penalty 3 (CP-SAT OPTIMAL) · booking score 67/70 · 0 priority inversions · exam penalty 0 |
| `exports/schedule_after.json` (sample disruption) | 0 hard violations · 12 sessions moved: **1 time-slot change, 11 room-only** · 177 unchanged · proven minimum (objective = bound) |
Reproduce: `cd source_files/extracted/CrunchWeek_StarterPack && python validator.py --data data/cit_public.json --schedule ../../../exports/schedule.json`
Test counts and the honest requirement-by-requirement status: `IMPLEMENTATION_STATUS.md` and `docs/REQUIREMENTS_AUDIT.md`.

## Architecture
```
 React + Vite + Tailwind (frontend/) ──HTTPS──> FastAPI (backend/app)
   role-based routes, floating Campus Buddy         ├─ api/routes      thin HTTP layer, backend authorisation on every endpoint
                                                    ├─ services/accounts      scrypt hashing, sign-in, access requests, password reset
                                                    ├─ services/scheduling    CP-SAT model + soft-score mirror
                                                    ├─ services/validation    official validator.py via subprocess
                                                    ├─ services/bookings      deterministic engine, week state, displacement
                                                    ├─ services/exams | disruptions | ai (Gemini client, parser, explain, Buddy)
                                                    └─ SQLAlchemy + Alembic ── SQLite (local) / PostgreSQL (production)
 Official starter pack: source_files/ (preserved, never modified)
```
Stack: Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic, OR-Tools; React 18, Vite 5, Tailwind 3, React Router, Recharts, Lucide, Inter (bundled).

## Setup
```
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && PYTHONPATH=. uvicorn app.main:app --port 8000      # migrates the database on start; docs at /docs
# second terminal
cd frontend && npm ci && npm run dev                             # http://localhost:5173
```
**Database**: SQLite file by default (`backend/var/campusx.db`). For PostgreSQL set `DATABASE_URL=postgresql+psycopg2://...`; the app runs `alembic upgrade head` at startup and refuses to start if the schema does not match the models.
**First start**: demo accounts are created if the users table is empty, and `exports/schedule.json` is loaded (re-validated by the official validator) as the starting timetable. Live changes are never overwritten on restart; the Admin *Settings -> Reset demo data* button restores the clean state (Admin only).
**Create a real Admin** (Admin cannot self-register): `CREATE_ADMIN_PASSWORD='...' python scripts/create_admin.py --email dean@college.edu --name "Dean's Office"`.
**Logo**: the supplied OptiCampus emblem is used everywhere (sidebar, landing, sign-in pages, favicon). The untouched original is `docs/branding/OptiCampus_Academic_Emblem.original.png`; the app serves a 512 px copy of the same artwork at `frontend/src/assets/logo.png` (replace that file to change the logo). It sits in a round white badge so it reads correctly in dark mode.
Regenerate exports: `python scripts/generate_exports.py timetable --time 240` (repeat to improve) then `python scripts/generate_exports.py export` (writes only if the validator accepts).

## Run locally on Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd backend
$env:PYTHONPATH = "."
uvicorn app.main:app --port 8000          # leave running; API docs at http://localhost:8000/docs
```
Second PowerShell window:
```powershell
cd frontend
npm ci
npm run dev                                # http://localhost:5173
```
Tests: backend `cd <repo root>; $env:PYTHONPATH=""; pytest` · frontend (needs the backend above running) `cd frontend; $env:VITE_API_BASE_URL="http://localhost:8000"; npx vitest run` · build `npm run build` · contrast `python scripts\contrast_check.py`.

## 5-minute demo script
1. Open the site: a 1-second glass splash (logo + name) pulls down to reveal the login page. Sign in as `admin@opticampus.demo`. 2. **Timetable Generator** -> run -> see the official validator verdict -> **Approve**. 3. **Exams** -> Publish. 4. Sign in as `student@opticampus.demo`, open the floating **Campus Buddy**, tap *When is my midsem?* (and *Exam kab hai?*). 5. As `club@opticampus.demo` -> **Request a Venue**: type *Need a room for 45 people on Tuesday 6 to 8 pm, projector please*, edit, submit; then request the same auditorium slot as BR-01 (Mon P4-5) to see a blocked conflict with an alternative. 6. As `faculty@opticampus.demo` -> **Schedule Assistant**: *I am unavailable on <a teaching day> because of a conference* -> review options -> Submit. 7. Back as admin -> **Schedule Changes** -> Review the request -> Approve (or Reject); timetable changes only now. 8. Show **Notifications** for each role and the admin **Overview**.

## Demo accounts (seeded; password = `DEMO_PASSWORD`, default `campusx-demo` for local use only)
| Email | Role |
|---|---|
| `admin@opticampus.demo` | Admin (Dean's Office) |
| `coordinator@opticampus.demo` | Department Coordinator (CSE) |
| `faculty@opticampus.demo` | Faculty (F01) |
| `club@opticampus.demo` | Club Representative |
| `student@opticampus.demo` | Read-only student view (not an approval role) |
These are **not shown on the sign-in page**. For any shared deployment set `DEMO_PASSWORD` and `LOCAL_AUTH_SECRET`; with `APP_ENV=production` the app refuses to seed demo accounts using the old default password.

## Authentication
Sign in (email + password, show/hide, remember me) · Request access (Faculty / Department Coordinator / Club Representative only; Admin cannot be requested; pending until an Admin approves) · Forgot/reset password (single-use, 30-minute token stored hashed; identical response for any email; sent by SMTP, or in development logged to the server console only) · Change password in Settings. Roles are enforced in the backend.

## Environment variables
See `.env.example` (backend) and `frontend/.env.example` (`VITE_API_BASE_URL`). Secrets are backend-only.

## Deployment (prepared, NOT performed)
- **Render (API)**: `render.yaml`; health check `/api/health`. Set `DATABASE_URL` (PostgreSQL), `LOCAL_AUTH_SECRET`, `DEMO_PASSWORD`, `CORS_ORIGINS`, `FRONTEND_URL`, optional `SMTP_*`, `GEMINI_API_KEY`; create the Admin with `scripts/create_admin.py`.
- **Vercel (web)**: root `frontend`, `VITE_API_BASE_URL=https://<service>.onrender.com`; `vercel.json` handles routing.
- Never commit real keys, database passwords or secrets.

## Known limitations
See `IMPLEMENTATION_STATUS.md`. Headlines: pages were never viewed in a real browser; PostgreSQL, SMTP and live Gemini were not exercised; nothing is deployed; the dataset is loaded from the official JSON (admin edits persist as a database snapshot, not normalised tables).
