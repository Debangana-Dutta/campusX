# Campus X — One Campus. Zero Clashes. Smarter Decisions.

Campus scheduling and venue management for CIT (Crunch Week). **AI interprets and assists; deterministic backend code
decides and validates.** This repository currently contains the **backend foundation (Part 1)**. The frontend, Gemini
assistant, notifications and deployment are Part 2 and do **not exist yet**.

## Verified results (official `validator.py`, unmodified)
| Export | Hard violations | Soft penalty | Booking score | Notes |
|---|---|---|---|---|
| `exports/schedule.json` | 0 | 3 (S4 only) | 67 / 70, 0 priority inversions | exam penalty 0 |
| `exports/schedule_after.json` (sample disruption) | 0 | 3 | 67 | 12 sessions moved (4 time, 8 room-only) |

Reproduce: `cd source_files/extracted/CrunchWeek_StarterPack && python validator.py --data data/cit_public.json --schedule ../../../exports/schedule.json`

## Architecture
```
 React/Vite UI (Part 2) ──HTTP──> FastAPI (backend/app)
                                    ├─ services/dataset      load + integrity checks (official JSON = source of truth)
                                    ├─ services/scheduling   OR-Tools CP-SAT: hard constraints + S1-S6 objective
                                    ├─ services/exams        CP-SAT, half-capacity multi-room allocation
                                    ├─ services/bookings     deterministic priority/caps/displacement engine
                                    ├─ services/disruptions  minimum-movement repair (pin -> free-all, lexicographic)
                                    ├─ services/validation   runs the OFFICIAL validator.py as a subprocess (--json)
                                    └─ SQLAlchemy (SQLite local / Supabase Postgres) — users, bookings, audit, versions
```
Stack: Python 3.12, FastAPI, Pydantic, SQLAlchemy, OR-Tools CP-SAT.

## Setup
```
python -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && PYTHONPATH=. uvicorn app.main:app --port 8000      # docs at /docs
pytest                                                           # from repo root: 71 tests
```
Extract the starter ZIP to `source_files/extracted/` (already done; original ZIP preserved in `source_files/`).
Generate exports (each step validates with the official validator and refuses to write on failure):
```
python scripts/generate_exports.py timetable --time 240     # repeat to keep improving (warm-started)
python scripts/generate_exports.py export
```

## Demo accounts (LOCAL DEVELOPMENT AUTH — not production authentication)
`POST /api/auth/local-login` with password `campusx-demo` (override via `DEMO_PASSWORD`) and username
`admin`, `faculty` (F01), `coordinator` (CSE), `club` (Dramatics Society). Roles are enforced in the backend.
Set `AUTH_MODE=supabase` to verify Supabase JWTs instead (role from `app_metadata.role`; users cannot self-assign).

## Key API endpoints
`GET /api/health` · `GET /api/dataset/status|summary` · `POST /api/dataset/import` · `POST /api/timetable/generate` ·
`GET /api/timetable[/group|faculty|room/{id}]` · `POST /api/timetable/validate` · `GET /api/timetable/export` ·
`GET|POST /api/bookings` · `GET /api/bookings/{id}` · `POST /api/bookings/{id}/decision|cancel` ·
`GET /api/exams` · `POST /api/exams/generate` · `GET /api/disruptions` · `POST /api/disruptions/preview` ·
`POST /api/disruptions/apply?did=` · `GET /api/disruptions/{id}/comparison` · `GET /api/reports/room-utilisation|validation`

## Known limitations
See `IMPLEMENTATION_STATUS.md` (authoritative).
