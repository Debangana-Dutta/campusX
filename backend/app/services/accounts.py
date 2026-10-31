"""Accounts: scrypt password hashing, sign-in, access requests, password reset (single-use time-limited tokens)."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import logging
import re
import secrets
import smtplib
from email.message import EmailMessage

from sqlalchemy import select

from app.config import get_settings
from app.models.db import PasswordReset, User, session_scope

log = logging.getLogger("campusx.accounts")
OFFICIAL_ROLES = ("admin", "faculty", "department_coordinator", "club_representative")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
DEMO_DOMAIN = "opticampus.demo"
DEMO = [  # (username, role, name, department, faculty_id, group_id, organisation)
    ("admin", "admin", "Dean's Office", None, None, None, None),
    ("faculty", "faculty", "Dr. Ananya Mishra", "CSE", "F01", None, None),
    ("coordinator", "department_coordinator", "CSE Coordinator", "CSE", None, None, None),
    ("club", "club_representative", "Dramatics Society", None, None, None, "Dramatics Society"),
    ("student", "student", "CSE Year 2 Student", "CSE", None, "CSE-2", None),
]


# ------------------------------------------------------------------ hashing
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(h).decode()


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, h = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, base64.b64decode(h))
    except Exception:  # noqa: BLE001  malformed hash -> never authenticates
        return False


def password_problem(pw: str) -> str | None:
    if len(pw) < 10:
        return "Password must be at least 10 characters"
    if not (re.search(r"[A-Za-z]", pw) and re.search(r"\d", pw)):
        return "Password must contain letters and at least one number"
    return None


def normalise_identifier(ident: str) -> str:
    i = ident.strip().lower()
    return i if "@" in i else f"{i}@{DEMO_DOMAIN}"       # legacy short usernames map to the seeded demo accounts


def email_problem(email: str) -> str | None:
    if not EMAIL_RE.match(email):
        return "Enter a valid email address"
    doms = [d.strip().lower() for d in get_settings().allowed_email_domains.split(",") if d.strip()]
    if doms and email.split("@")[1].lower() not in doms:
        return f"Use your institutional email ({', '.join('@' + d for d in doms)})"
    return None


# ------------------------------------------------------------------ seeding
def seed_demo_users() -> int:
    st = get_settings()
    if not st.seed_demo_users:
        return 0
    if st.app_env == "production" and st.demo_password == "campusx-demo":
        log.error("refusing to seed demo users in production with the default demo password; set DEMO_PASSWORD")
        return 0
    n = 0
    with session_scope() as s:
        if s.scalar(select(User.id).limit(1)):
            return 0                                     # never overwrite existing accounts
        for u, role, name, dept, fid, gid, org in DEMO:
            email = f"{u}@{DEMO_DOMAIN}"
            s.add(User(id=email, email=email, name=name, role=role, status="active", department=dept, faculty_id=fid,
                       group_id=gid, organisation=org, password_hash=hash_password(st.demo_password)))
            n += 1
    return n


# ------------------------------------------------------------------ account requests
def request_access(name: str, email: str, password: str, role: str, department=None, faculty_id=None, organisation=None) -> User:
    email = email.strip().lower()
    if role not in OFFICIAL_ROLES:
        raise ValueError("Choose one of the four official roles")
    if role == "admin":
        raise PermissionError("Admin accounts cannot be requested. They are created by an existing administrator.")
    for p in (email_problem(email), password_problem(password), None if len(name.strip()) >= 2 else "Enter your full name"):
        if p:
            raise ValueError(p)
    with session_scope() as s:
        if s.get(User, email):
            raise FileExistsError("An account or request already exists for this email")
        u = User(id=email, email=email, name=name.strip()[:120], role=role, requested_role=role, status="pending",
                 password_hash=hash_password(password), department=department, faculty_id=faculty_id, organisation=organisation)
        s.add(u)
        from app.services.audit import notify
        notify.notify("role:admin", f"{u.name} ({email}) requested a {role.replace('_', ' ')} account.", "account",
                      "/app/users", sender=email, related_id=email, dedupe=f"account-request:{email}", session=s)
    return u


# ------------------------------------------------------------------ password reset
def _send_email(to: str, subject: str, body: str) -> bool:
    st = get_settings()
    if not st.smtp_host:
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = st.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(st.smtp_host, st.smtp_port, timeout=15) as c:
            c.starttls()
            if st.smtp_user:
                c.login(st.smtp_user, st.smtp_password)
            c.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("password-reset email failed: %s", type(e).__name__)
        return False


def start_password_reset(email: str) -> None:
    """Always silent about whether the address exists (no account enumeration)."""
    st = get_settings()
    email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    with session_scope() as s:
        u = s.get(User, email)
        if not u or u.status != "active":
            return
        s.add(PasswordReset(user_id=u.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                            expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=st.reset_token_ttl_min)))
        name = u.name
    link = f"{st.frontend_url.rstrip('/')}/reset-password?token={token}"
    sent = _send_email(email, "Reset your OptiCampus password",
                       f"Hello {name},\n\nUse this link to set a new password (valid for {st.reset_token_ttl_min} minutes, one use):\n{link}\n\n"
                       "If you did not ask for this, ignore this email.")
    if not sent:
        if st.app_env == "production":
            log.warning("password reset requested but SMTP is not configured; no link was delivered")
        else:   # DEVELOPMENT ONLY: surface the link in the server log so the flow can be tested without email
            log.warning("DEV ONLY - password reset link for %s: %s", email, link)


def complete_password_reset(token: str, new_password: str) -> bool:
    if (p := password_problem(new_password)):
        raise ValueError(p)
    h = hashlib.sha256(token.encode()).hexdigest()
    now = dt.datetime.now(dt.timezone.utc)
    with session_scope() as s:
        r = s.scalar(select(PasswordReset).where(PasswordReset.token_hash == h))
        if not r or r.used_at is not None or r.expires_at.replace(tzinfo=dt.timezone.utc) < now:
            return False
        u = s.get(User, r.user_id)
        if not u or u.status != "active":
            return False
        u.password_hash = hash_password(new_password)
        r.used_at = now                                    # single use
        for other in s.scalars(select(PasswordReset).where(PasswordReset.user_id == u.id, PasswordReset.used_at.is_(None))):
            other.used_at = now                            # invalidate any other outstanding tokens
    return True


def authenticate(identifier: str, password: str) -> User | None:
    email = normalise_identifier(identifier)
    with session_scope() as s:
        u = s.get(User, email)
        ok = verify_password(password, u.password_hash if u else hash_password("x"))   # constant-ish time either way
        return u if (u and ok) else None
