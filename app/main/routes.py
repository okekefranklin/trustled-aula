"""Main blueprint: dashboard plus the features shared by lecturers and students
(the sanctioned research assistant and the reference formatter)."""
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from ..llm_service import generate

main_bp = Blueprint("main", __name__)


def _style():
    """The institution's house referencing style, applied across features."""
    inst = current_user.institution
    return inst.referencing_style if inst else "APA"


@main_bp.route("/")
@login_required
def dashboard():
    return render_template("main/dashboard.html")


@main_bp.route("/assistant", methods=["GET", "POST"])
@login_required
def assistant():
    """Sanctioned AI chat/research assistant. Generates research and project
    ideas from a user's stated interests, with references in the house style."""
    result = None
    interests = ""
    field = ""
    if request.method == "POST":
        interests = request.form.get("interests", "").strip()
        field = request.form.get("field", "").strip()
        style = _style()
        prompt = (
            f"A {current_user.role} in the field of '{field}' is exploring research "
            f"and project ideas. Their interests: {interests}.\n\n"
            "Suggest 4 to 6 focused, original research or project ideas. For each, "
            "give a working title, a one-paragraph rationale, a suggested approach, "
            f"and 1 to 2 illustrative references formatted in {style} style. "
            "Make the ideas realistic for an academic setting."
        )
        result = generate("research_ideas", prompt,
                          system="You are an academic research advisor helping "
                                 "staff and students develop sound, original ideas.")
    return render_template("main/assistant.html", result=result,
                           interests=interests, field=field, style=_style())


@main_bp.route("/references", methods=["GET", "POST"])
@login_required
def references():
    """Format raw source details into the institution's referencing style."""
    result = None
    sources = ""
    if request.method == "POST":
        sources = request.form.get("sources", "").strip()
        style = _style()
        prompt = (
            f"Format the following source details as a reference list in {style} "
            f"style. Return only the formatted references, one per line, in "
            f"alphabetical order.\n\nSources:\n{sources}"
        )
        result = generate("reference_format", prompt,
                          system="You are a meticulous academic editor who formats "
                                 "references precisely in the requested style.")
    return render_template("main/references.html", result=result,
                           sources=sources, style=_style())
