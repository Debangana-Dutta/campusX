"""SQLAlchemy models + engine. SQLite locally; Supabase PostgreSQL when DATABASE_URL points at it.

Original dataset records are NOT stored here (they live in the preserved source files); this database holds
user-generated application records only: profiles/roles, booking requests, timetable versions, exam runs,
disruptions, notifications and the audit trail.
"""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager

from sqlalchemy import JSON, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import get_settings


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)          # Supabase auth user id / local username
    display_name: Mapped[str] = mapped_column(String(120))
    department: Mapped[str | None] = mapped_column(String(40), nullable=True)
    faculty_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    organisation: Mapped[str | None] = mapped_column(String(120), nullable=True)  # e.g. club name


class RoleAssignment(Base):
    """Roles are assigned by an admin only; nobody can self-assign (enforced in the API)."""
    __tablename__ = "role_assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(32))   # admin | faculty | department_coordinator | club_representative
    granted_by: Mapped[str] = mapped_column(String(64))
    granted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BookingRecord(Base):
    __tablename__ = "bookings"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    requester_id: Mapped[str] = mapped_column(String(64), index=True)
    request: Mapped[dict] = mapped_column(JSON)       # structured request (same shape as dataset booking_requests)
    decision: Mapped[dict] = mapped_column(JSON)      # engine decision (status/room/day/periods/reason/...)
    state: Mapped[str] = mapped_column(String(24), default="proposed")  # proposed|confirmed|rejected|cancelled
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TimetableVersion(Base):
    __tablename__ = "timetable_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(24))     # generated | disruption
    solver_status: Mapped[str] = mapped_column(String(24))
    validated: Mapped[bool] = mapped_column(default=False)
    hard_violations: Mapped[int] = mapped_column(Integer, default=-1)
    soft_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schedule: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ExamRun(Base):
    """One exam-scheduling run (the full exam list as exported, plus its solver status and penalty)."""
    __tablename__ = "exam_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    solver_status: Mapped[str] = mapped_column(String(24))
    penalty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exams: Mapped[list] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DisruptionRecord(Base):
    __tablename__ = "disruptions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    changes: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24))   # previewed | applied | rejected | infeasible
    proposal: Mapped[dict] = mapped_column(JSON)
    requested_by: Mapped[str] = mapped_column(String(64))
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)   # audience: user id | "role:<role>" | "*"
    message: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32), default="info")
    link: Mapped[str | None] = mapped_column(String(120), nullable=True)
    read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class NotificationRead(Base):
    """Per-user read receipts so broadcast notifications can be read independently."""
    __tablename__ = "notification_reads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    notification_id: Mapped[int] = mapped_column(Integer, index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), index=True)
    subject: Mapped[str] = mapped_column(String(80), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


_engine = None
_Session = None


def init_db(url: str | None = None) -> None:
    global _engine, _Session
    st = get_settings()
    url = url or st.database_url
    if url.startswith("sqlite"):
        st.state_dir.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(url, future=True, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(_engine, expire_on_commit=False)


@contextmanager
def session_scope():
    if _Session is None:
        init_db()
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def record_version(kind: str, solver_status: str, validated: bool, hard: int, soft: int | None,
                   schedule: dict, created_by: str = "system", exam_status: str | None = None,
                   exam_penalty: int | None = None) -> None:
    """Persist a timetable version (+ the exam run inside it) for history/audit. Failure must not break the request."""
    import logging
    try:
        with session_scope() as s:
            s.add(TimetableVersion(kind=kind, solver_status=solver_status, validated=validated, hard_violations=hard,
                                   soft_total=soft, schedule=schedule, created_by=created_by))
            if schedule.get("exams"):
                s.add(ExamRun(solver_status=exam_status or "n/a", penalty=exam_penalty, exams=schedule["exams"], created_by=created_by))
    except Exception:  # noqa: BLE001
        logging.getLogger("campusx.db").exception("could not record timetable version")
