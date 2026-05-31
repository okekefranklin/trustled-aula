"""Lecturer-only features: lesson planning aligned to the semester calendar,
and lecture note generation."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from ..decorators import lecturer_required
from ..extensions import db
from ..llm_service import generate
from ..models import LessonPlan, LectureNote

lecturer_bp = Blueprint("lecturer", __name__, url_prefix="/lecturer")


@lecturer_bp.route("/plans")
@login_required
@lecturer_required
def plans():
    items = LessonPlan.query.filter_by(user_id=current_user.id)\
        .order_by(LessonPlan.created_at.desc()).all()
    notes = LectureNote.query.filter_by(user_id=current_user.id)\
        .order_by(LectureNote.created_at.desc()).all()
    return render_template("lecturer/plans.html", plans=items, notes=notes)


@lecturer_bp.route("/plan/new", methods=["GET", "POST"])
@login_required
@lecturer_required
def new_plan():
    result = None
    form = {}
    if request.method == "POST":
        form = {
            "module": request.form.get("module", "").strip(),
            "topics": request.form.get("topics", "").strip(),
            "weeks": request.form.get("weeks", "").strip(),
            "session_length": request.form.get("session_length", "").strip(),
        }
        prompt = (
            f"Create a structured lesson plan for the module '{form['module']}'.\n"
            f"Topics to cover: {form['topics']}.\n"
            f"The plan spans {form['weeks']} weeks of the semester, with each "
            f"session lasting {form['session_length']}.\n\n"
            "For each week, give the topic, learning objectives, a session outline "
            "with timing, suggested activities, and any preparation required. "
            "Align the sequence so it builds logically across the semester."
        )
        result = generate("lesson_plan", prompt,
                          system="You are an experienced curriculum designer "
                                 "creating clear, practical lesson plans.")
        if request.form.get("save") and result:
            plan = LessonPlan(user_id=current_user.id, module=form["module"],
                              title=f"{form['module']} — semester plan", content=result)
            db.session.add(plan)
            db.session.commit()
            flash("Lesson plan saved.", "success")
            return redirect(url_for("lecturer.plans"))
    return render_template("lecturer/new_plan.html", result=result, form=form)


@lecturer_bp.route("/note/new", methods=["GET", "POST"])
@login_required
@lecturer_required
def new_note():
    result = None
    topic = ""
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        detail = request.form.get("detail", "").strip()
        prompt = (
            f"Write structured lecture notes on the topic: '{topic}'.\n"
            f"Additional context or scope: {detail}.\n\n"
            "Organise into clear sections with headings, key concepts, worked "
            "examples or illustrations where useful, and a short summary of the "
            "main takeaways at the end. Write for delivery to students."
        )
        result = generate("lecture_note", prompt,
                          system="You are a subject lecturer preparing clear, "
                                 "well-structured teaching notes.")
        if request.form.get("save") and result:
            note = LectureNote(user_id=current_user.id, topic=topic, content=result)
            db.session.add(note)
            db.session.commit()
            flash("Lecture note saved.", "success")
            return redirect(url_for("lecturer.plans"))
    return render_template("lecturer/new_note.html", result=result, topic=topic)
