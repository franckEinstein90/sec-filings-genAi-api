import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("OPENAI_API_KEY", "")

from sec_filings.app import create_app  # noqa: E402
from sec_filings.db.session import get_session  # noqa: E402
from tests.fakes import FakeEdgarClient  # noqa: E402


@pytest.fixture(scope="session")
def pgdata() -> Path:
    return Path(tempfile.mkdtemp(prefix="sec-filings-pg-"))


@pytest.fixture(scope="session")
def app(pgdata):
    return create_app(testing=True, pgdata=pgdata)


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def fake_edgar(monkeypatch):
    fake = FakeEdgarClient()

    def _factory(*_args, **_kwargs):
        return fake

    monkeypatch.setattr("sec_filings.services.ingest.EdgarClient", _factory)
    monkeypatch.setattr("sec_filings.edgar.client.EdgarClient", _factory)
    return fake


@pytest.fixture()
def db_session(app):
    session = get_session()
    try:
        yield session
    finally:
        session.close()
