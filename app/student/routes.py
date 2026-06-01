"""Student-only features: research/project support and exam preparation."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from ..decorators import student_required
from ..extensions import db
from ..llm_service import generate
from ..models import StudentDocument
from ..quota import quota_status
from ..research_service import (all_sources_unavailable_message,
                                format_papers_bibliography, format_papers_for_prompt,
                                search_papers)

student_bp = Blueprint("student", __name__, url_prefix="/student")


def _style():
    inst = current_user.institution
    return inst.referencing_style if inst else "APA"


@student_bp.route("/work")
@login_required
@student_required
def work():
    docs = StudentDocument.query.filter_by(user_id=current_user.id)\
        .order_by(StudentDocument.created_at.desc()).all()
    return render_template("student/work.html", docs=docs,
                           quota=quota_status(current_user))


@student_bp.route("/research/new", methods=["GET", "POST"])
@login_required
@student_required
def new_research():
    result = None
    form = {}
    papers = []
    used_research_api = False
    research_source = None
    if request.method == "POST":
        form = {
            "course": request.form.get("course", "").strip(),
            "interests": request.form.get("interests", "").strip(),
            "stage": request.form.get("stage", "ideas"),
        }
        style = _style()
        search_query = f"{form['course']} {form['interests']}".strip()
        papers, used_research_api, research_source = search_papers(search_query)

        if used_research_api:
            sources_block = format_papers_for_prompt(papers)
            prompt = (
                f"A student on the course '{form['course']}' needs research support.\n"
                f"Their interests: {form['interests']}.\n"
                f"Stage of work: {form['stage']}.\n\n"
                f"The following papers were retrieved from {research_source} (real, "
                "verifiable sources — each has a verification link). Use these sources "
                "in your guidance — do not invent citations.\n\n"
                f"{sources_block}\n\n"
                "Provide focused, practical help appropriate to that stage, drawing on "
                "the retrieved papers where relevant. Include 2 to 3 references from "
                f"the sources above, formatted in {style} style, with verification links. "
                "Encourage original thinking and do not write the work for them.\n\n"
                "End with a section titled 'Real retrieved sources' listing only the "
                "papers above that you referenced. Label each as REAL and include its "
                "verification link."
            )
            system = (
                "You are a supportive academic mentor. Use only the retrieved papers "
                "provided — never fabricate references. Clearly label every citation as "
                "REAL and include its verification URL."
            )
        else:
            prompt = (
                f"A student on the course '{form['course']}' needs research support.\n"
                f"Their interests: {form['interests']}.\n"
                f"Stage of work: {form['stage']}.\n\n"
                "Provide focused, practical help appropriate to that stage: if ideas, "
                "suggest viable project topics with rationales; if outlining, propose a "
                "structure; if drafting, offer guidance and pointers. Include 2 to 3 "
                f"illustrative references in {style} style. Encourage original thinking "
                "and do not write the work for them.\n\n"
                f"Note: {all_sources_unavailable_message()}"
            )
            system = (
                "You are a supportive academic mentor guiding a student to do "
                "their own strong work."
            )

        result = generate("student_research", prompt, system=system)
        if used_research_api and result and not result.startswith("You have reached"):
            bib = format_papers_bibliography(papers, style)
            result = f"{result}\n\n---\n{bib}"
        if request.form.get("save") and result:
            doc = StudentDocument(user_id=current_user.id, kind="research",
                                  title=f"Research support — {form['course']}",
                                  content=result)
            db.session.add(doc)
            db.session.commit()
            flash("Saved to your work.", "success")
            return redirect(url_for("student.work"))
    return render_template("student/new_research.html", result=result,
                           form=form, style=_style(),
                           used_research_api=used_research_api, papers=papers,
                           research_source=research_source)


@student_bp.route("/exam/new", methods=["GET", "POST"])
@login_required
@student_required
def new_exam():
    result = None
    form = {}
    if request.method == "POST":
        form = {
            "subject": request.form.get("subject", "").strip(),
            "topics": request.form.get("topics", "").strip(),
        }
        prompt = (
            f"Create exam preparation material for '{form['subject']}'.\n"
            f"Topics: {form['topics']}.\n\n"
            "Produce a concise revision summary of the key points, then 8 to 10 "
            "practice questions of mixed difficulty, followed by model answers or "
            "marking guidance in a separate section so the student can self-test."
        )
        result = generate("exam_prep", prompt,
                          system="You are a tutor creating effective, accurate "
                                 "revision and practice material.")
        if request.form.get("save") and result:
            doc = StudentDocument(user_id=current_user.id, kind="exam_prep",
                                  title=f"Exam prep — {form['subject']}",
                                  content=result)
            db.session.add(doc)
            db.session.commit()
            flash("Saved to your work.", "success")
            return redirect(url_for("student.work"))
    return render_template("student/new_exam.html", result=result, form=form)
