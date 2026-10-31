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
# dataset booking `role` value for each platform role
DATASET_ROLE = {"admin": "admin", "faculty": "faculty", "department_coordinator": "department_coordinator",
                "club_representative": "club"}

DEMO_USERS = {
    "admin": {"role": "admin", "name": "Dean's Office (demo)", "department": None, "faculty_id": None, "org": None},
    "faculty": {"role": "faculty", "name": "Dr. Ananya Mishra (demo)", "department": "CSE", "faculty_id": "F01", "org": None},
    "coordinator": {"role": "department_coordinator", "name": "CSE Coordinator (demo)", "department": "CSE", "faculty_id": None, "org": None},
    "club": {"role": "club_representative", "name": "Dramatics Society (demo)", "department": None, "faculty_id": None, "org": "Dramatics Society"},
}


@dataclass
class User:
    id: str
    role: str
    name: str
    department: str | None = None
    faculty_id: str | None = None
    org: str | None = None
    mode: str = "local"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_local_token(username: str, ttl_s: int = 8 * 3600) -> str:
    body = _b64(json.dumps({"sub": username, "exp": int(time.time()) + ttl_s}).encode())
    sig = _b64(hmac.new(get_settings().local_auth_secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def _verify_local(token: str) -> User:
    try:
        body, sig = token.split(".")
        good = _b64(hmac.new(get_settings().local_auth_secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            raise ValueError("bad signature")
        claims = json.loads(_unb64(body))
        if claims["exp"] < time.time():
            raise ValueError("expired")
        u = DEMO_USERS[claims["sub"]]
    except Exception as e:  # noqa: BLE001
        raise HTTPException(401, "invalid or expired token") from e
    return User(claims["sub"], u["role"], u["name"], u["department"], u["faculty_id"], u["org"], "local")


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
        if role not in ROLES:
            raise ValueError("no valid role assigned")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(401, "invalid token") from e
    return User(c["sub"], role, c.get("email", c["sub"]), meta.get("department"), meta.get("faculty_id"),
                meta.get("organisation"), "supabase")


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
