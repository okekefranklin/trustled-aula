"""Per-user token quota helpers."""
from datetime import date, datetime, timedelta

from sqlalchemy import func

from .extensions import db
from .models import AuditLog


def _period_start(user):
    """Effective start of the user's current quota period."""
    if user.quota_period_start:
        return user.quota_period_start
    return date.today().replace(day=1)


def tokens_used(user):
    """Sum prompt + completion tokens from audit logs since period start."""
    start = _period_start(user)
    since = datetime.combine(start, datetime.min.time())
    total = db.session.query(
        func.coalesce(
            func.sum(AuditLog.prompt_tokens + AuditLog.completion_tokens), 0
        )
    ).filter(
        AuditLog.user_id == user.id,
        AuditLog.created_at >= since,
    ).scalar()
    return int(total or 0)


def quota_reset_date(user):
    """When the current quota period ends (30-day rolling window)."""
    return _period_start(user) + timedelta(days=30)


def is_over_quota(user):
    quota = user.token_quota if user.token_quota is not None else 100000
    return tokens_used(user) >= quota


def quota_status(user):
    """Dict for templates and route handlers."""
    used = tokens_used(user)
    quota = user.token_quota if user.token_quota is not None else 100000
    return {
        "used": used,
        "quota": quota,
        "remaining": max(0, quota - used),
        "reset_date": quota_reset_date(user),
        "over_quota": used >= quota,
    }
