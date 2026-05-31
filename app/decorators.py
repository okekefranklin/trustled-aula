"""Role-based access control."""
from functools import wraps

from flask import abort
from flask_login import current_user

from .models import ROLE_ADMIN, ROLE_LECTURER, ROLE_STUDENT


def role_required(*roles):
    """Restrict a view to one or more roles.

    Usage:
        @role_required(ROLE_LECTURER)
        def view(): ...
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


admin_required = role_required(ROLE_ADMIN)
lecturer_required = role_required(ROLE_LECTURER)
student_required = role_required(ROLE_STUDENT)
