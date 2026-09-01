"""Start a pip-installable Postgres 16 server that already includes pgvector."""

from __future__ import annotations

import logging
from pathlib import Path

from sec_filings.config import PGDATA_DIR, sqlalchemy_url_from_postgres

logger = logging.getLogger(__name__)

_server = None


def start_embedded_postgres(pgdata: Path | None = None, db_name: str | None = None):
    """Start (or reuse) an embedded Postgres datadir and return (server, sqlalchemy_url)."""
    global _server
    import pgserver

    data_dir = Path(pgdata or PGDATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting embedded Postgres in %s", data_dir)
    _server = pgserver.get_server(str(data_dir), cleanup_mode="stop")
    try:
        _server.psql("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception as exc:
        logger.debug("Could not create vector extension via psql yet: %s", exc)

    uri = _server.get_uri()
    if db_name:
        uri = _replace_db_name(uri, db_name)
    return _server, sqlalchemy_url_from_postgres(uri)


def get_embedded_server():
    return _server


def _replace_db_name(uri: str, db_name: str) -> str:
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(uri)
    return urlunparse(parsed._replace(path=f"/{db_name}"))
