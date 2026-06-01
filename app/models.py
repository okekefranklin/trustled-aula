"""Database models for TrustLed Aula.

Four core tables:
  - Institution: per-university settings, including the referencing style that
    every feature applies by default.
  - User: staff and students, with one of three roles.
  - AuditLog: a record of every AI interaction, which is what makes the
    platform "governed" rather than just another AI tool.
  - Artefact tables (LessonPlan, LectureNote, StudentDocument): the saved
    outputs of each feature, tied to the user who created them.
"""
from datetime import date, datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db, login_manager
from .policies import DEFAULT_POLICY_VERSION

# Role constants
ROLE_ADMIN = "admin"
ROLE_LECTURER = "lecturer"
ROLE_STUDENT = "student"
ROLES = (ROLE_ADMIN, ROLE_LECTURER, ROLE_STUDENT)


class Institution(db.Model):
    __tablename__ = "institutions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    # The house referencing style applied across all features by default.
    referencing_style = db.Column(db.String(50), default="APA", nullable=False)
    policy_version = db.Column(db.String(20), default=DEFAULT_POLICY_VERSION, nullable=False)
    acceptable_use_policy = db.Column(db.Text)
    data_privacy_notice = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship("User", backref="institution", lazy=True)

    def __repr__(self):
        return f"<Institution {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STUDENT)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    institution_id = db.Column(db.Integer, db.ForeignKey("institutions.id"))

    token_quota = db.Column(db.Integer, default=100000, nullable=False)
    quota_period_start = db.Column(db.Date, default=lambda: date.today().replace(day=1))

    accepted_policies_at = db.Column(db.DateTime, nullable=True)
    policy_version = db.Column(db.String(20), nullable=True)

    # Helpers
    def has_accepted_current_policy(self):
        """True if the user accepted the institution's current policy version."""
        inst = self.institution
        if not inst:
            return self.accepted_policies_at is not None
        required = inst.policy_version or DEFAULT_POLICY_VERSION
        return (
            self.accepted_policies_at is not None
            and self.policy_version == required
        )
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def is_lecturer(self):
        return self.role == ROLE_LECTURER

    @property
    def is_student(self):
        return self.role == ROLE_STUDENT

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class AuditLog(db.Model):
    """One row per AI interaction. This is the governance backbone: who used
    what feature, when, what they asked, which model answered, and how many
    tokens it cost. Admins read this; nobody can use the AI without writing here.
    """
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user_email = db.Column(db.String(200))   # denormalised for fast log reads
    role = db.Column(db.String(20))
    feature = db.Column(db.String(80))        # e.g. "research_ideas", "lesson_plan"
    model = db.Column(db.String(80))
    prompt = db.Column(db.Text)               # capped in the service layer
    prompt_tokens = db.Column(db.Integer, default=0)
    completion_tokens = db.Column(db.Integer, default=0)
    blocked = db.Column(db.Boolean, default=False)  # set if a request was filtered/failed
    note = db.Column(db.String(255))          # e.g. error reason or filter reason
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User", backref="audit_logs")

    def __repr__(self):
        return f"<AuditLog {self.user_email} {self.feature} {self.created_at}>"


class LessonPlan(db.Model):
    __tablename__ = "lesson_plans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    module = db.Column(db.String(200))
    title = db.Column(db.String(255))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="lesson_plans")


class LectureNote(db.Model):
    __tablename__ = "lecture_notes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    topic = db.Column(db.String(255))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="lecture_notes")


class StudentDocument(db.Model):
    __tablename__ = "student_documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    kind = db.Column(db.String(50))   # "research", "exam_prep"
    title = db.Column(db.String(255))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="student_documents")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
