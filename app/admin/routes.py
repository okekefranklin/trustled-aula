"""Admin blueprint: account management, the audit log, usage analytics, and
institution settings. This is where the governance value is visible."""
import csv
import io
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, Response)
from flask_login import login_required, current_user
from sqlalchemy import func

from ..decorators import admin_required
from ..extensions import db
from ..models import (User, AuditLog, Institution, ROLES, ROLE_ADMIN,
                      ROLE_LECTURER, ROLE_STUDENT)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    # Headline usage figures
    total_calls = AuditLog.query.count()
    by_feature = db.session.query(
        AuditLog.feature, func.count(AuditLog.id)
    ).group_by(AuditLog.feature).order_by(func.count(AuditLog.id).desc()).all()
    by_role = db.session.query(
        AuditLog.role, func.count(AuditLog.id)
    ).group_by(AuditLog.role).all()
    blocked = AuditLog.query.filter_by(blocked=True).count()
    user_count = User.query.count()
    return render_template("admin/dashboard.html", total_calls=total_calls,
                           by_feature=by_feature, by_role=by_role,
                           blocked=blocked, user_count=user_count)


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    items = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=items, roles=ROLES)


@admin_bp.route("/users/new", methods=["POST"])
@login_required
@admin_required
def new_user():
    email = request.form.get("email", "").strip().lower()
    name = request.form.get("full_name", "").strip()
    role = request.form.get("role", ROLE_STUDENT)
    password = request.form.get("password", "")

    if not email or not name or not password or role not in ROLES:
        flash("Please complete all fields with a valid role.", "danger")
        return redirect(url_for("admin.users"))
    if User.query.filter_by(email=email).first():
        flash("A user with that email already exists.", "warning")
        return redirect(url_for("admin.users"))

    inst = Institution.query.first()
    user = User(email=email, full_name=name, role=role,
                institution_id=inst.id if inst else None)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f"Account created for {email}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_user(user_id):
    user = db.session.get(User, user_id)
    if user and user.id != current_user.id:
        user.is_active_user = not user.is_active_user
        db.session.commit()
        flash(f"{user.email} is now "
              f"{'active' if user.is_active_user else 'inactive'}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/audit")
@login_required
@admin_required
def audit():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    query = AuditLog.query
    if q:
        query = query.filter(AuditLog.user_email.ilike(f"%{q}%"))
    if role in ROLES:
        query = query.filter(AuditLog.role == role)
    logs = query.order_by(AuditLog.created_at.desc()).limit(300).all()
    return render_template("admin/audit.html", logs=logs, q=q, role=role, roles=ROLES)


@admin_bp.route("/audit/export")
@login_required
@admin_required
def audit_export():
    """Download the full audit log as CSV for offline review or evidence."""
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "user_email", "role", "feature", "model",
                     "prompt_tokens", "completion_tokens", "blocked", "note"])
    for log in logs:
        writer.writerow([
            log.created_at.isoformat() if log.created_at else "",
            log.user_email, log.role, log.feature, log.model,
            log.prompt_tokens, log.completion_tokens, log.blocked, log.note or "",
        ])
    filename = f"aula_audit_{datetime.utcnow():%Y%m%d_%H%M}.csv"
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    inst = Institution.query.first()
    if request.method == "POST" and inst:
        inst.name = request.form.get("name", inst.name).strip()
        inst.referencing_style = request.form.get("referencing_style",
                                                   inst.referencing_style).strip()
        db.session.commit()
        flash("Institution settings updated.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html", inst=inst)
