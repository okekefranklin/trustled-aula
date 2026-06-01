"""Main blueprint: dashboard plus the features shared by lecturers and students
(the sanctioned research assistant and the reference formatter)."""
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from ..decorators import staff_required
from ..llm_service import generate
from ..research_service import (all_sources_unavailable_message,
                                format_papers_bibliography, format_papers_for_prompt,
                                search_papers)

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
@staff_required
def assistant():
    """Sanctioned AI chat/research assistant. Generates research and project
    ideas from a user's stated interests, with references in the house style."""
    result = None
    interests = ""
    field = ""
    papers = []
    used_research_api = False
    research_source = None
    if request.method == "POST":
        interests = request.form.get("interests", "").strip()
        field = request.form.get("field", "").strip()
        style = _style()
        search_query = f"{field} {interests}".strip()
        papers, used_research_api, research_source = search_papers(search_query)

        if used_research_api:
            sources_block = format_papers_for_prompt(papers)
            prompt = (
                f"A {current_user.role} in the field of '{field}' is exploring research "
                f"and project ideas. Their interests: {interests}.\n\n"
                f"The following papers were retrieved from {research_source} (real, "
                "verifiable sources — each has a verification link). Base your suggestions "
                "on these sources only — do not invent citations.\n\n"
                f"{sources_block}\n\n"
                "Suggest 4 to 6 focused, original research or project ideas informed by "
                "these sources. For each, give a working title, a one-paragraph rationale, "
                "a suggested approach, and cite 1 to 2 of the retrieved sources above "
                f"formatted in {style} style, including each source's verification link.\n\n"
                "End with a section titled 'Real retrieved sources' listing only the papers "
                "above that you referenced. Label each as REAL and include its verification "
                "link so the user can click through to the original."
            )
            system = (
                "You are an academic research advisor. Use only the retrieved papers "
                "provided — never fabricate references. Clearly label every citation as "
                "REAL and include its verification URL."
            )
        else:
            prompt = (
                f"A {current_user.role} in the field of '{field}' is exploring research "
                f"and project ideas. Their interests: {interests}.\n\n"
                "Suggest 4 to 6 focused, original research or project ideas. For each, "
                "give a working title, a one-paragraph rationale, a suggested approach, "
                f"and 1 to 2 illustrative references formatted in {style} style. "
                "Make the ideas realistic for an academic setting.\n\n"
                f"Note: {all_sources_unavailable_message()}"
            )
            system = (
                "You are an academic research advisor helping staff and students "
                "develop sound, original ideas."
            )

        result = generate("research_ideas", prompt, system=system)
        if used_research_api and result and not result.startswith("You have reached"):
            bib = format_papers_bibliography(papers, style)
            result = f"{result}\n\n---\n{bib}"
    return render_template("main/assistant.html", result=result,
                           interests=interests, field=field, style=_style(),
                           used_research_api=used_research_api, papers=papers,
                           research_source=research_source)


@main_bp.route("/references", methods=["GET", "POST"])
@login_required
@staff_required
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
