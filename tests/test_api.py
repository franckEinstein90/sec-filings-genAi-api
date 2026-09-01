from io import BytesIO

from sec_filings.services.ingest import ingest_ticker, ingest_upload


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_reports_pgvector(client):
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["pgvector"]


def test_openapi_docs(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"] == "SEC Filings GenAI API"
    assert "/api/v1/filings/ingest" in spec["paths"]


def test_ingest_and_query_roundtrip(client, fake_edgar):
    ingest = client.post(
        "/api/v1/filings/ingest",
        json={"ticker": "AAPL", "form_types": ["10-K"], "limit": 1},
    )
    assert ingest.status_code == 201, ingest.text
    payload = ingest.json()
    assert payload["company"]["ticker"] == "AAPL"
    stored = payload["ingested"] or payload["skipped"]
    assert stored
    filing_id = stored[0]["filing"]["id"]

    listed = client.get("/api/v1/filings?ticker=AAPL")
    assert listed.status_code == 200
    assert listed.json()["filings"]

    queried = client.post(
        "/api/v1/query",
        json={"prompt": "What risk factors are disclosed?", "ticker": "AAPL"},
    )
    assert queried.status_code == 200, queried.text
    body = queried.json()
    assert body["answer"]
    assert body["citations"]
    assert body["citations"][0]["filing_id"] == filing_id
    assert body["citations"][0]["ticker"] == "AAPL"


def test_upload_html_filing(client, fake_edgar):
    response = client.post(
        "/api/v1/filings/upload",
        data={"ticker": "MSFT", "form_type": "10-Q"},
        files={
            "file": (
                "msft.htm",
                BytesIO(b"<html><body>Item 2. MD&A Azure growth continued.</body></html>"),
                "text/html",
            )
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["filing"]["processing_status"] == "ready"


def test_portfolio_holdings(client, fake_edgar):
    created = client.post("/api/v1/portfolios", json={"name": "Tech", "description": "demo"})
    assert created.status_code == 201
    portfolio_id = created.json()["portfolio"]["id"]

    added = client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"ticker": "AAPL", "shares": 10},
    )
    assert added.status_code == 201, added.text
    watchlist = client.get("/api/v1/portfolio")
    assert watchlist.status_code == 200
    assert watchlist.json()["portfolio"]["name"] == "Watchlist"


def test_query_requires_prompt(client):
    response = client.post("/api/v1/query", json={})
    assert response.status_code == 400


def test_ingest_helpers_use_injected_client(fake_edgar):
    result = ingest_ticker("AAPL", form_types=["10-K"], limit=1, client=fake_edgar)
    assert result["company"]["ticker"] == "AAPL"
    stored = result["ingested"] or result["skipped"]
    assert stored[0]["filing"]["chunk_count"] > 0

    uploaded = ingest_upload(
        ticker="AAPL",
        filename="note.txt",
        payload=b"Item 1A. Risk Factors\nCurrency fluctuation may affect results.",
        form_type="8-K",
        content_type="text/plain",
    )
    assert uploaded["filing"]["source"] == "upload"
