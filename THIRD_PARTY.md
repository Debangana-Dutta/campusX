# Third-party software

## Backend (Python 3.12) — see `backend/requirements.txt` for exact versions
Google OR-Tools (CP-SAT solver, Apache-2.0) · FastAPI/Starlette (MIT/BSD) · Pydantic + pydantic-settings (MIT) · SQLAlchemy + Alembic (MIT) · Uvicorn (BSD) ·
hashlib.scrypt (Python standard library, password hashing) · smtplib (standard library, password-reset email) · httpx (BSD, Gemini REST calls and tests) · psycopg2-binary (LGPL, PostgreSQL driver for Supabase) · python-multipart (Apache-2.0) · pytest (MIT) · numpy, pandas, protobuf (BSD; OR-Tools dependencies)

## Frontend — see `frontend/package.json` and `package-lock.json`
React, React DOM, React Router (MIT) · Vite + @vitejs/plugin-react (MIT) · Tailwind CSS, PostCSS, Autoprefixer (MIT) · Framer Motion (MIT) · Recharts (MIT) · Lucide React (ISC) ·
@fontsource-variable/inter (Inter font, SIL Open Font License 1.1, bundled locally) · Vitest, @testing-library/react, @testing-library/jest-dom, jsdom (MIT)
Note: the UI components (cards, buttons, dialogs, tabs) are written in-house in a claymorphism style; **shadcn/ui is not used**.

## Official materials (unmodified)
CIT starter pack: `validator.py`, `cit_public.json`, CSVs and examples (organisers). No code from earlier projects or other hackathons was used. No fonts or images are loaded from external hosts.
