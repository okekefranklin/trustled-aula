"""Central LLM service.

This is the single gateway through which every AI request in Aula passes.
No feature talks to a model directly; they all call ``generate()`` here. That
gives the platform two things at once:

  1. Governance. Every call is written to the AuditLog before the result is
     returned, so the institution has a complete, attributable record of AI
     use across staff and students.
  2. Swappable providers. Switching between Anthropic and OpenAI (or to a
     self-hosted model) is a change in one place, driven by environment
     variables, not a rewrite across the app.

If no API key is configured, the service runs in a safe "stub" mode that
returns a clearly-labelled placeholder. That lets you run and demo the whole
app, and exercise the logging, without spending on API calls. Set LLM_API_KEY
to switch to live generation.
"""
from datetime import datetime

from flask import current_app
from flask_login import current_user

from .extensions import db
from .models import AuditLog
from .quota import is_over_quota, quota_status


def _log(feature, prompt, model, p_tokens=0, c_tokens=0, blocked=False, note=None):
    """Write one governance record. Never lets a logging error break a request."""
    try:
        cap = current_app.config.get("AUDIT_PROMPT_CAP", 4000)
        entry = AuditLog(
            user_id=current_user.id,
            user_email=current_user.email,
            role=current_user.role,
            feature=feature,
            model=model,
            prompt=(prompt or "")[:cap],
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            blocked=blocked,
            note=note,
            created_at=datetime.utcnow(),
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:  # pragma: no cover - logging must not crash the feature
        db.session.rollback()


def _call_anthropic(system, prompt, model, api_key):
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    usage = resp.usage
    return text, usage.input_tokens, usage.output_tokens


def _call_openai(system, prompt, model, api_key, base_url=None):
    from openai import OpenAI

    if base_url:
        client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    text = resp.choices[0].message.content
    usage = resp.usage
    return text, usage.prompt_tokens, usage.completion_tokens


def generate(feature, prompt, system="You are a helpful academic assistant."):
    """Run a governed AI request and return the text result.

    ``feature`` is a short tag (e.g. "lesson_plan") used in the audit log so
    admins can see which tools are in use.
    """
    cfg = current_app.config
    provider = cfg.get("LLM_PROVIDER", "anthropic")
    model = cfg.get("LLM_MODEL", "")
    api_key = cfg.get("LLM_API_KEY", "")

    if is_over_quota(current_user):
        status = quota_status(current_user)
        note = (
            f"Quota exceeded: {status['used']:,}/{status['quota']:,} tokens used "
            f"this period (resets {status['reset_date'].strftime('%d %b %Y')})"
        )
        _log(feature, prompt, model=model or "n/a", blocked=True, note=note)
        return (
            "You have reached your AI token quota for this period. "
            f"Your allowance resets on {status['reset_date'].strftime('%d %B %Y')}. "
            "Please contact your administrator if you need more."
        )

    # Stub mode: no key configured. Still logs, so governance can be demonstrated.
    if not api_key:
        _log(feature, prompt, model="stub", note="No API key configured")
        return (
            "[Aula is running in demo mode because no AI provider key is set. "
            "Add LLM_API_KEY to enable live generation.]\n\n"
            "Your request was received and logged for governance:\n\n"
            f"{prompt}"
        )

    try:
        if provider == "openai":
            base_url = cfg.get("LLM_BASE_URL") or None
            text, p_tok, c_tok = _call_openai(
                system, prompt, model, api_key, base_url=base_url
            )
        else:
            text, p_tok, c_tok = _call_anthropic(system, prompt, model, api_key)
        _log(feature, prompt, model=model, p_tokens=p_tok, c_tokens=c_tok)
        return text
    except Exception as exc:  # surface a clean message, record the failure
        _log(feature, prompt, model=model, blocked=True, note=str(exc)[:240])
        return (
            "Aula could not complete this request. The attempt has been logged. "
            "Please try again, and contact your administrator if it continues."
        )
