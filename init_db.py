"""Initialise the database and seed one institution and three test accounts,
one per role. Run once after setup:

    python init_db.py

Re-running is safe: it will not duplicate accounts that already exist.
"""
from app import create_app
from app.extensions import db
from app.models import Institution, User, ROLE_ADMIN, ROLE_LECTURER, ROLE_STUDENT
from app.policies import (DEFAULT_ACCEPTABLE_USE, DEFAULT_POLICY_VERSION,
                          DEFAULT_PRIVACY_NOTICE)

app = create_app()

SEED_USERS = [
    ("admin@aula.test", "Aula Administrator", ROLE_ADMIN, "admin123"),
    ("lecturer@aula.test", "Dr Sample Lecturer", ROLE_LECTURER, "lecturer123"),
    ("student@aula.test", "Sample Student", ROLE_STUDENT, "student123"),
]

with app.app_context():
    db.create_all()

    inst = Institution.query.first()
    if not inst:
        inst = Institution(
            name="Demo University",
            referencing_style="APA",
            policy_version=DEFAULT_POLICY_VERSION,
            acceptable_use_policy=DEFAULT_ACCEPTABLE_USE,
            data_privacy_notice=DEFAULT_PRIVACY_NOTICE,
        )
        db.session.add(inst)
        db.session.commit()
        print(f"Created institution: {inst.name}")

    for email, name, role, pw in SEED_USERS:
        if not User.query.filter_by(email=email).first():
            u = User(email=email, full_name=name, role=role, institution_id=inst.id)
            u.set_password(pw)
            db.session.add(u)
            print(f"Created {role}: {email} / {pw}")
    db.session.commit()
    print("\nSeed complete. Sign in at /login with any account above.")
