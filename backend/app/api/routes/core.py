"""Health, auth (local dev mode), dataset endpoints."""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.core.auth import User, current_user, issue_local_token, require_roles
from app.models.db import User as UserRow, session_scope
from app.schemas.api import AccessRequestIn, ChangePasswordIn, ForgotIn, LoginIn, ResetIn
from app.services import accounts
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


def _login(body: LoginIn):
    st = get_settings()
    if st.auth_mode != "local":
        raise HTTPException(404, "password sign-in is disabled when AUTH_MODE=supabase")
    ident = body.email or body.username or ""
    u = accounts.authenticate(ident, body.password)
    if u is None:
        # a pending account gets a specific, safe message only AFTER the password was right
        with session_scope() as s:
            row = s.get(UserRow, accounts.normalise_identifier(ident))
            if row and row.status == "pending" and accounts.verify_password(body.password, row.password_hash):
                raise HTTPException(403, "Your account request is waiting for approval by the admin office.")
        raise HTTPException(401, "Incorrect email or password")
    if u.status == "pending":
        raise HTTPException(403, "Your account request is waiting for approval by the admin office.")
    if u.status != "active":
        raise HTTPException(403, "This account is not active.")
    audit.record(u.id, "auth.login", u.id, {})
    ttl = 30 * 24 * 3600 if body.remember else 8 * 3600
    return {"token": issue_local_token(u.id, ttl), "role": u.role, "name": u.name}


@router.post("/auth/login")
def login(body: LoginIn):
    return _login(body)


@router.post("/auth/local-login")      # kept for backward compatibility with earlier clients/tests
def local_login(body: LoginIn):
    return _login(body)


@router.post("/auth/request-access", status_code=201)
def request_access(body: AccessRequestIn):
    try:
        u = accounts.request_access(body.name, body.email, body.password, body.role, body.department, body.faculty_id, body.organisation)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except FileExistsError as e:
        raise HTTPException(409, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    audit.record(u.id, "auth.request_access", u.id, {"role": u.requested_role})
    return {"status": "pending", "message": "Request sent. An administrator will review it; you can sign in once it is approved."}


@router.post("/auth/forgot-password")
def forgot_password(body: ForgotIn):
    accounts.start_password_reset(body.email)
    return {"message": "If that email is registered, a reset link has been sent."}      # identical either way


@router.post("/auth/reset-password")
def reset_password(body: ResetIn):
    try:
        ok = accounts.complete_password_reset(body.token, body.new_password)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if not ok:
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
    return {"message": "Password updated. You can now sign in."}


@router.post("/auth/change-password")
def change_password(body: ChangePasswordIn, user: User = Depends(current_user)):
    if (p := accounts.password_problem(body.new_password)):
        raise HTTPException(422, p)
    with session_scope() as s:
        row = s.get(UserRow, user.id)
        if not row or not accounts.verify_password(body.current_password, row.password_hash):
            raise HTTPException(403, "Current password is incorrect")
        row.password_hash = accounts.hash_password(body.new_password)
    audit.record(user.id, "auth.change_password", user.id, {})
    return {"message": "Password changed"}


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
