"""Authentication: login and logout. Account creation is handled by an admin
in the admin blueprint, since this is a governed, institution-controlled
platform rather than an open sign-up service."""
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db
from ..models import Institution, User

auth_bp = Blueprint("auth", __name__)


def _institution():
    inst = current_user.institution if current_user.is_authenticated else None
    return inst or Institution.query.first()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.has_accepted_current_policy():
            return redirect(url_for("main.dashboard"))
        return redirect(url_for("auth.consent"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password) and user.is_active_user:
            login_user(user)
            if user.has_accepted_current_policy():
                return redirect(url_for("main.dashboard"))
            return redirect(url_for("auth.consent"))
        flash("Invalid credentials, or your account is inactive.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/consent", methods=["GET", "POST"])
@login_required
def consent():
    inst = _institution()
    if current_user.has_accepted_current_policy():
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        if not request.form.get("accept_aup") or not request.form.get("accept_privacy"):
            flash("You must accept both policies to continue.", "danger")
            return render_template("auth/consent.html", inst=inst)

        required = inst.policy_version if inst else "1.0"
        current_user.accepted_policies_at = datetime.utcnow()
        current_user.policy_version = required
        db.session.commit()
        flash("Thank you. You may now use Aula.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/consent.html", inst=inst)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))
