"""Application factory for TrustLed Aula."""
from flask import Flask, render_template

from config import Config
from .extensions import db, login_manager
from .consent import require_policy_consent


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from .auth.routes import auth_bp
    from .main.routes import main_bp
    from .lecturer.routes import lecturer_bp
    from .student.routes import student_bp
    from .admin.routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(lecturer_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    app.before_request(require_policy_consent)

    # Error pages
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403,
                               message="You do not have access to that page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404,
                               message="That page was not found."), 404

    # Create tables on first run if they do not exist (SQLite convenience).
    with app.app_context():
        db.create_all()
        _ensure_schema_columns()
        _seed_policy_defaults()

    return app


def _ensure_schema_columns():
    """Add columns to existing databases without a full migration."""
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    tables = insp.get_table_names()

    if "users" in tables:
        cols = {c["name"] for c in insp.get_columns("users")}
        stmts = []
        if "token_quota" not in cols:
            stmts.append("ALTER TABLE users ADD COLUMN token_quota INTEGER DEFAULT 100000")
        if "quota_period_start" not in cols:
            stmts.append("ALTER TABLE users ADD COLUMN quota_period_start DATE")
        if "accepted_policies_at" not in cols:
            stmts.append("ALTER TABLE users ADD COLUMN accepted_policies_at DATETIME")
        if "policy_version" not in cols:
            stmts.append("ALTER TABLE users ADD COLUMN policy_version VARCHAR(20)")
        if stmts:
            with db.engine.begin() as conn:
                for stmt in stmts:
                    conn.execute(text(stmt))

    if "institutions" in tables:
        cols = {c["name"] for c in insp.get_columns("institutions")}
        stmts = []
        if "policy_version" not in cols:
            stmts.append(
                "ALTER TABLE institutions ADD COLUMN policy_version VARCHAR(20) DEFAULT '1.0'"
            )
        if "acceptable_use_policy" not in cols:
            stmts.append("ALTER TABLE institutions ADD COLUMN acceptable_use_policy TEXT")
        if "data_privacy_notice" not in cols:
            stmts.append("ALTER TABLE institutions ADD COLUMN data_privacy_notice TEXT")
        if stmts:
            with db.engine.begin() as conn:
                for stmt in stmts:
                    conn.execute(text(stmt))


def _seed_policy_defaults():
    """Ensure the institution has editable policy placeholder text."""
    from .models import Institution
    from .policies import (DEFAULT_ACCEPTABLE_USE, DEFAULT_POLICY_VERSION,
                           DEFAULT_PRIVACY_NOTICE)

    inst = Institution.query.first()
    if not inst:
        return
    changed = False
    if not inst.policy_version:
        inst.policy_version = DEFAULT_POLICY_VERSION
        changed = True
    if not inst.acceptable_use_policy:
        inst.acceptable_use_policy = DEFAULT_ACCEPTABLE_USE
        changed = True
    if not inst.data_privacy_notice:
        inst.data_privacy_notice = DEFAULT_PRIVACY_NOTICE
        changed = True
    if changed:
        db.session.commit()


def _ensure_quota_columns():
    """Deprecated alias kept for compatibility."""
    _ensure_schema_columns()
