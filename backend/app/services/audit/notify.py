"""In-app notifications created from REAL backend events (never seeded/faked)."""
from __future__ import annotations

from sqlalchemy import select

from app.models.db import Notification, NotificationRead, session_scope


def notify(audience: str, message: str, kind: str = "info", link: str | None = None, *, sender: str | None = None,
           related_id: str | None = None, dedupe: str | None = None, session=None) -> bool:
    """audience: a user id, 'role:<role>' or '*' (everyone). Pass `session` to join the caller's transaction so a
    failed request never leaves a half-saved record. `dedupe` makes the same event notify only once."""
    def _add(s) -> bool:
        if dedupe and s.scalar(select(Notification.id).where(Notification.dedupe_key == dedupe)):
            return False
        s.add(Notification(user_id=audience, message=message, kind=kind, link=link, sender=sender,
                           related_id=related_id, dedupe_key=dedupe))
        return True
    if session is not None:
        return _add(session)
    with session_scope() as s:
        return _add(s)


def _audiences(user) -> list[str]:
    aud = [user.id, f"role:{user.role}", "*"]
    if user.role == "department_coordinator" and user.department:
        aud.append(f"coord:{user.department}")          # messages meant for this department's coordinator(s)
    return aud


def list_for(user, limit: int = 100) -> dict:
    with session_scope() as s:
        rows = list(s.scalars(select(Notification).where(Notification.user_id.in_(_audiences(user)))
                              .order_by(Notification.id.desc()).limit(limit)))
        read = set(s.scalars(select(NotificationRead.notification_id).where(NotificationRead.user_id == user.id)))
        items = [{"id": n.id, "message": n.message, "kind": n.kind, "link": n.link, "sender": n.sender, "related_id": n.related_id,
                  "read": n.id in read, "created_at": n.created_at.isoformat()} for n in rows]
    return {"unread": sum(1 for i in items if not i["read"]), "items": items}


def mark_read(user, ids: list[int] | None = None) -> int:
    cur = list_for(user, 500)["items"]
    todo = [i["id"] for i in cur if not i["read"] and (ids is None or i["id"] in ids)]
    with session_scope() as s:
        for nid in todo:
            s.add(NotificationRead(user_id=user.id, notification_id=nid))
    return len(todo)
