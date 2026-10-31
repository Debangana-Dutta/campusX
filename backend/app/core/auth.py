"""Authentication/authorisation.

AUTH_MODE=local    -> clearly-labelled DEVELOPMENT stub: fixed demo accounts + HMAC-signed tokens.
AUTH_MODE=supabase -> verifies Supabase JWTs (HS256, SUPABASE_JWT_SECRET) and reads the role from the
                      `app_metadata.role` claim, which only the backend/admin can set (users cannot self-assign).
Authorisation is always enforced here in the backend, never trusted from the client.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Header, HTTPException

from app.config import get_settings

ROLES = ("admin", "faculty", "department_coordinator", "club_representative")
STUDENT = "student"   # read-only experience; never an approval role
# dataset booking `role` value for each platform role
DATASET_ROLE = {"admin": "admin", "faculty": "faculty", "department_coordinator": "department_coordinator",
                "club_representative": "club"}


@dataclass
class User:
    id: str
    role: str
    name: str
    department: str | None = None
    faculty_id: str | None = None
    org: str | None = None
    mode: str = "local"
    group_id: str | None = None


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_local_token(user_id: str, ttl_s: int = 8 * 3600) -> str:
    body = _b64(json.dumps({"sub": user_id, "exp": int(time.time()) + ttl_s}).encode())
    sig = _b64(hmac.new(get_settings().local_auth_secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def _verify_local(token: str) -> User:
    from app.models.db import User as UserRow, session_scope
    try:
        body, sig = token.split(".")
        good = _b64(hmac.new(get_settings().local_auth_secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            raise ValueError("bad signature")
        claims = json.loads(_unb64(body))
        if claims["exp"] < time.time():
            raise ValueError("expired")
        with session_scope() as s:
            u = s.get(UserRow, claims["sub"])
            if not u or u.status != "active":
                raise ValueError("inactive account")
            return User(u.id, u.role, u.name, u.department, u.faculty_id, u.organisation, "local", u.group_id)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(401, "invalid or expired token") from e


def _verify_supabase(token: str) -> User:
    st = get_settings()
    if not st.supabase_jwt_secret:
        raise HTTPException(503, "Supabase auth selected but SUPABASE_JWT_SECRET is not configured")
    try:
        h, b, sig = token.split(".")
        good = _b64(hmac.new(st.supabase_jwt_secret.encode(), f"{h}.{b}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            raise ValueError("bad signature")
        c = json.loads(_unb64(b))
        if c.get("exp", 0) < time.time():
            raise ValueError("expired")
        meta = c.get("app_metadata", {})
        role = meta.get("role")
        if role not in ROLES + (STUDENT,):
            raise ValueError("no valid role assigned")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(401, "invalid token") from e
    return User(c["sub"], role, c.get("email", c["sub"]), meta.get("department"), meta.get("faculty_id"),
                meta.get("organisation"), "supabase", meta.get("group_id"))


def current_user(authorization: str | None = Header(default=None)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    return _verify_supabase(token) if get_settings().auth_mode == "supabase" else _verify_local(token)


def require_roles(*roles: str) -> Callable[[User], User]:
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"role '{user.role}' may not perform this action (needs one of {list(roles)})")
        return user
    return dep
