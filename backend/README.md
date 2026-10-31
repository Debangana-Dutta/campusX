# Campus X backend
FastAPI service. Run from this directory: `PYTHONPATH=. uvicorn app.main:app --port 8000` (interactive docs at `/docs`).
- `app/services/*` hold all business logic (dataset, scheduling, exams, bookings, disruptions, validation, audit); routes in `app/api/routes` only translate HTTP.
- Database: SQLite by default; set `DATABASE_URL` for Supabase PostgreSQL. Migrations: `alembic upgrade head` (initial schema included; `alembic revision --autogenerate` after model changes).
- Tests live in `../tests` (`pytest` from the repo root). The official `validator.py` is run as a subprocess and never modified.
- Configuration: see `../.env.example`.
