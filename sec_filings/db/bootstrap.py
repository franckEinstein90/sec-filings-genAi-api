"""Create the database, enable pgvector, and apply Alembic migrations."""

from __future__ import annotations

import logging
from pathlib import Path

from pgvector.psycopg import register_vector
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from sec_filings.config import DATABASE_URL, ROOT_DIR, sqlalchemy_url_from_postgres
from sec_filings.db.session import configure_engine

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database has not been bootstrapped. Call bootstrap_database().")
    return _engine


def bootstrap_database(
    database_url: str | None = None,
    pgdata: Path | None = None,
    run_migrations: bool = True,
) -> Engine:
    """
    Connect to Postgres.

    If DATABASE_URL (or database_url) is set, use that server.
    Otherwise start the embedded pgserver binary (includes the vector extension).
    """
    global _engine

    url = database_url or DATABASE_URL
    if url:
        sqlalchemy_url = sqlalchemy_url_from_postgres(url)
        logger.info("Using Postgres at DATABASE_URL")
    else:
        from sec_filings.db.embedded import start_embedded_postgres

        _, sqlalchemy_url = start_embedded_postgres(pgdata=pgdata)
        logger.info("Using embedded Postgres")

    engine = create_engine(sqlalchemy_url, pool_pre_ping=True)
    _register_pgvector(engine)
    _ensure_vector_extension(engine)

    if run_migrations:
        apply_migrations(engine)

    configure_engine(engine)
    _engine = engine
    return engine


def apply_migrations(engine: Engine) -> None:
    from alembic import command
    from alembic.config import Config

    ini_path = ROOT_DIR / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", _render_url(engine))
    command.upgrade(cfg, "head")
    logger.info("Alembic migrations applied")


def _render_url(engine: Engine) -> str:
    return engine.url.render_as_string(hide_password=False).replace("%", "%%")


def _register_pgvector(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _connection_record):  # noqa: ANN001
        try:
            register_vector(dbapi_connection)
        except Exception:
            logger.debug("pgvector already registered on connection", exc_info=True)


def _ensure_vector_extension(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    engine = bootstrap_database()
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar()
        ext = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
    print(f"Connected: {version}")
    print(f"pgvector: {ext}")
    print(f"URL: {engine.url.render_as_string(hide_password=True)}")


if __name__ == "__main__":
    main()
