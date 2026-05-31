"""Application factory for TrustLed Aula."""
from flask import Flask, render_template

from config import Config
from .extensions import db, login_manager


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

    return app
