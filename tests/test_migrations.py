from pathlib import Path

import pgserver
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from sec_filings.config import ROOT_DIR, sqlalchemy_url_from_postgres


def _migration_config(engine):
    cfg = Config(str(ROOT_DIR / "alembic.ini"))
    cfg.set_main_option(
        "sqlalchemy.url",
        engine.url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    return cfg


def test_alembic_upgrade_downgrade_upgrade_roundtrip(tmp_path: Path):
    server = pgserver.get_server(str(tmp_path / "migration-pg"), cleanup_mode="stop")
    engine = create_engine(sqlalchemy_url_from_postgres(server.get_uri()), pool_pre_ping=True)
    cfg = _migration_config(engine)

    command.upgrade(cfg, "head")

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert {"companies", "filings", "filing_chunks", "portfolios", "holdings"} <= tables

    with engine.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        vector_version = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one()
    assert revision == "001_initial_sec_pgvector"
    assert vector_version

    chunk_indexes = {idx["name"] for idx in inspector.get_indexes("filing_chunks")}
    assert "ix_filing_chunks_embedding" in chunk_indexes

    command.downgrade(cfg, "base")
    downgraded_tables = set(inspect(engine).get_table_names())
    assert "companies" not in downgraded_tables
    assert "filings" not in downgraded_tables
    assert "filing_chunks" not in downgraded_tables

    command.upgrade(cfg, "head")
    upgraded_tables = set(inspect(engine).get_table_names())
    assert {"companies", "filings", "filing_chunks"} <= upgraded_tables

    engine.dispose()
