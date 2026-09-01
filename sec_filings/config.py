"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or None
PGDATA_DIR = Path(os.getenv("PGDATA_DIR", ROOT_DIR / ".pgdata")).expanduser()
EMBEDDED_DB_NAME = os.getenv("EMBEDDED_DB_NAME", "sec_filings")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip() or None
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower()
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()

SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT",
    "sec-filings-genAi-api/0.2 (https://github.com/franckEinstein90/sec-filings-genAi-api)",
)
SEC_TICKERS_URL = os.getenv(
    "SEC_TICKERS_URL",
    "https://www.sec.gov/files/company_tickers.json",
)
SEC_SUBMISSIONS_URL = os.getenv(
    "SEC_SUBMISSIONS_URL",
    "https://data.sec.gov/submissions/CIK{cik}.json",
)
SEC_ARCHIVES_BASE = os.getenv(
    "SEC_ARCHIVES_BASE",
    "https://www.sec.gov/Archives/edgar/data",
)

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "8"))
INGEST_DEFAULT_LIMIT = int(os.getenv("INGEST_DEFAULT_LIMIT", "3"))
MAX_DOWNLOAD_BYTES = int(os.getenv("MAX_DOWNLOAD_BYTES", str(20 * 1024 * 1024)))

SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))

DEFAULT_FORM_TYPES = ("10-K", "10-Q", "8-K")


def sqlalchemy_url_from_postgres(uri: str) -> str:
    """Force the psycopg3 SQLAlchemy dialect."""
    if uri.startswith("postgresql+psycopg://"):
        return uri
    if uri.startswith("postgresql://"):
        return "postgresql+psycopg://" + uri[len("postgresql://") :]
    if uri.startswith("postgres://"):
        return "postgresql+psycopg://" + uri[len("postgres://") :]
    return uri
