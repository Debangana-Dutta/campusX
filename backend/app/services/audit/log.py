"""Audit trail: every state-changing action is recorded with actor, action, subject and detail."""
from __future__ import annotations

import logging
from typing import Any

from app.models.db import AuditEvent, session_scope

log = logging.getLogger("campusx.audit")


def record(actor: str, action: str, subject: str = "", detail: dict[str, Any] | None = None) -> None:
    with session_scope() as s:
        s.add(AuditEvent(actor=actor, action=action, subject=subject, detail=detail or {}))
    log.info("audit actor=%s action=%s subject=%s", actor, action, subject)


def recent(limit: int = 100, subject: str | None = None) -> list[dict[str, Any]]:
    from sqlalchemy import select
    with session_scope() as s:
        q = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
        if subject:
            q = q.where(AuditEvent.subject == subject)
        return [{"id": e.id, "actor": e.actor, "action": e.action, "subject": e.subject,
                 "detail": e.detail, "at": e.at.isoformat()} for e in s.scalars(q)]
