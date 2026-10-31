"""Health, auth (local dev mode), dataset endpoints."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.core.auth import DEMO_USERS, User, current_user, issue_local_token, require_roles
from app.schemas.api import LoginIn
from app.services.audit import log as audit
from app.services.dataset.loader import REFERENCE_COUNTS, sha256_file
from app.state import STATE

router = APIRouter()


@router.get("/health")
def health():
    st = get_settings()
    return {"status": "ok", "auth_mode": st.auth_mode, "dataset_loaded": STATE.imported,
            "validator_present": st.validator_path.exists(), "database": st.database_url.split(":")[0],
            "note": "auth_mode=local is a development stub, not production authentication" if st.auth_mode == "local" else ""}


@router.post("/auth/local-login")
def local_login(body: LoginIn):
    st = get_settings()
    if st.auth_mode != "local":
        raise HTTPException(404, "local login is disabled when AUTH_MODE=supabase")
    if body.username not in DEMO_USERS or not hmac.compare_digest(body.password, st.demo_password):
        raise HTTPException(401, "invalid credentials")
    u = DEMO_USERS[body.username]
    return {"token": issue_local_token(body.username), "role": u["role"], "name": u["name"],
            "mode": "LOCAL DEVELOPMENT AUTH - not production authentication"}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user.__dict__


@router.get("/dataset/status")
def dataset_status():
    st = get_settings()
    rep = STATE.integrity
    return {"imported": STATE.imported, "source": st.dataset_path.name,
            "source_sha256": sha256_file(st.dataset_path), "validator_sha256": sha256_file(st.validator_path),
            "dataset_id": STATE.raw.get("dataset_id"), "integrity": rep.as_dict() if rep else None,
            "reference_counts": REFERENCE_COUNTS, "disruptions_applied": len(STATE.applied_disruptions)}


@router.post("/dataset/import")
def dataset_import(reset: bool = False, user: User = Depends(require_roles("admin"))):
    rep = STATE.import_dataset(reset=reset)
    audit.record(user.id, "dataset.import", "cit_public.json", {"reset": reset, "ok": rep.ok})
    if not rep.ok:
        raise HTTPException(422, {"message": "dataset failed integrity checks; nothing was loaded", "errors": rep.errors[:50]})
    return {"ok": True, "reset": reset, "integrity": rep.as_dict()}


@router.get("/dataset/summary")
def dataset_summary(user: User = Depends(current_user)):
    _need_data()
    ds = STATE.ds
    return {"dataset_id": ds.raw["dataset_id"], "institute": ds.raw.get("institute"),
            "rooms": [{k: r[k] for k in ("id", "name", "type", "capacity", "accessible", "features", "allowed_uses")} for r in ds.rooms.values()],
            "faculty": [{"id": f["id"], "name": f["name"], "department": f["department"]} for f in ds.faculty.values()],
            "groups": list(ds.groups.values()), "calendar": ds.raw["calendar"],
            "counts": {"sessions": len(ds.sessions), "courses": len(ds.courses), "exams": len(ds.exams),
                       "booking_requests": len(ds.requests)}}


def _need_data():
    if not STATE.imported:
        raise HTTPException(409, "dataset not imported yet: POST /api/dataset/import")
