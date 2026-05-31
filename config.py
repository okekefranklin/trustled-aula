import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    """Base configuration. Values are read from environment variables so that
    nothing sensitive is committed to the repository."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

    # Database. Defaults to local SQLite for development. On Render/Railway set
    # DATABASE_URL to a Postgres connection string and it will be used instead.
    _db_url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'aula.db'}")
    # Render provides postgres:// URLs; SQLAlchemy needs postgresql://
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # LLM provider settings. The whole point of Aula is that AI access runs
    # through the server, so the key lives here and never reaches the browser.
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")  # anthropic | openai
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    LLM_MODEL = os.environ.get("LLM_MODEL", "claude-3-5-sonnet-20241022")

    # Max characters of a prompt we store in the audit log (full prompt kept,
    # but capped so a pasted document does not bloat the log).
    AUDIT_PROMPT_CAP = int(os.environ.get("AUDIT_PROMPT_CAP", "4000"))
