import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


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
    # Optional override for OpenAI-compatible APIs (e.g. Groq). Ignored unless
    # LLM_PROVIDER=openai.
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")

    # Max characters of a prompt we store in the audit log (full prompt kept,
    # but capped so a pasted document does not bloat the log).
    AUDIT_PROMPT_CAP = int(os.environ.get("AUDIT_PROMPT_CAP", "4000"))

    # Semantic Scholar (real scholarly search). Optional API key raises rate limits.
    SEMANTIC_SCHOLAR_BASE_URL = os.environ.get(
        "SEMANTIC_SCHOLAR_BASE_URL",
        "https://api.semanticscholar.org/graph/v1",
    )
    SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    SEMANTIC_SCHOLAR_MAX_RETRIES = int(os.environ.get("SEMANTIC_SCHOLAR_MAX_RETRIES", "4"))
    SEMANTIC_SCHOLAR_RETRY_BASE_SECONDS = float(
        os.environ.get("SEMANTIC_SCHOLAR_RETRY_BASE_SECONDS", "2.0")
    )
    SEMANTIC_SCHOLAR_MIN_INTERVAL = float(
        os.environ.get("SEMANTIC_SCHOLAR_MIN_INTERVAL", "1.05")
    )

    # Multi-source scholarly search (OpenAlex primary, Semantic Scholar, CrossRef).
    OPENALEX_BASE_URL = os.environ.get("OPENALEX_BASE_URL", "https://api.openalex.org")
    CROSSREF_BASE_URL = os.environ.get("CROSSREF_BASE_URL", "https://api.crossref.org")
    RESEARCH_CONTACT_EMAIL = os.environ.get("RESEARCH_CONTACT_EMAIL", "admin@aula.test")
    RESEARCH_SOURCE_ORDER = os.environ.get(
        "RESEARCH_SOURCE_ORDER",
        "OpenAlex,Semantic Scholar,CrossRef",
    )
