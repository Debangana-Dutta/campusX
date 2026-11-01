"""Campus X API. AI interprets and assists; deterministic backend code decides and validates."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import bookings, core, disruptions, exams, faculty_assistant, ops, platform, reports, timetable
from app.config import get_settings
from app.models.db import init_db
from app.state import STATE

st = get_settings()
logging.basicConfig(level=st.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("campusx")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if st.auth_mode == "local" and st.local_auth_secret == "dev-only-secret-change-me":
        log.warning("SECURITY: AUTH_MODE=local with the default LOCAL_AUTH_SECRET. Set LOCAL_AUTH_SECRET and DEMO_PASSWORD "
                    "before exposing this beyond local development; local auth is a demo stub, not production authentication.")
    from app.services import accounts
    log.info("seeded %d demo account(s)", accounts.seed_demo_users())
    rep = STATE.import_dataset()
    log.info("dataset import ok=%s counts=%s", rep.ok, rep.counts)
    if rep.ok and not STATE.assignment:
        import json
        ex = st.exports_dir / "schedule.json"
        if ex.exists():   # first start: load the app's own validated export so the UI is populated; re-validated here
            v = STATE.load_schedule(json.loads(ex.read_text()), "loaded_export", approver="system (validated export)")
            log.info("loaded exports/schedule.json; official validator accepted=%s", v.accepted)
    yield


app = FastAPI(title="Campus X", version="0.1.0", lifespan=lifespan,
              description="One Campus. Zero Clashes. Smarter Decisions.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in st.cors_origins.split(",")],
                   allow_methods=["*"], allow_headers=["*"])
for r in (core.router, timetable.router, bookings.router, exams.router, disruptions.router, reports.router, platform.router, ops.router, faculty_assistant.router):
    app.include_router(r, prefix="/api")


def _err(status: int, code: str, message, detail=None):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "detail": detail}})


@app.exception_handler(HTTPException)
async def http_exc(_: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return _err(exc.status_code, f"http_{exc.status_code}", exc.detail.get("message", "request failed"), exc.detail)
    return _err(exc.status_code, f"http_{exc.status_code}", exc.detail)


@app.exception_handler(RequestValidationError)
async def val_exc(_: Request, exc: RequestValidationError):
    detail = [{"loc": [str(x) for x in e.get("loc", [])], "msg": str(e.get("msg", "")), "type": e.get("type", "")}
              for e in exc.errors()]
    return _err(422, "validation_error", "request body failed validation", detail)


@app.exception_handler(Exception)
async def any_exc(_: Request, exc: Exception):
    log.exception("unhandled error")
    return _err(500, "internal_error", "internal server error")   # no paths/secrets leaked
