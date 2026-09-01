import httpx
import pytest

from sec_filings.edgar.client import EdgarClient, EdgarTransientError


class QueueHttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, _url):
        self.calls += 1
        return self.responses.pop(0)


def test_edgar_retries_rate_limit_then_succeeds():
    transport = QueueHttpClient(
        [
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, content=b"ok"),
        ]
    )
    client = EdgarClient(
        client=transport,
        min_interval=0,
        max_retries=1,
        retry_backoff=0,
    )

    response = client._get("https://data.sec.gov/example")

    assert response.status_code == 200
    assert transport.calls == 2


@pytest.mark.parametrize("status_code", [429, 503])
def test_edgar_transient_failure_is_bounded(status_code):
    transport = QueueHttpClient(
        [
            httpx.Response(status_code, headers={"Retry-After": "0"}),
            httpx.Response(status_code, headers={"Retry-After": "0"}),
        ]
    )
    client = EdgarClient(
        client=transport,
        min_interval=0,
        max_retries=1,
        retry_backoff=0,
    )

    with pytest.raises(EdgarTransientError, match="after 2 attempts"):
        client._get("https://data.sec.gov/example")

    assert transport.calls == 2


def test_ingest_endpoint_maps_exhausted_edgar_to_503(client, monkeypatch):
    def _fail(*_args, **_kwargs):
        raise EdgarTransientError("EDGAR remained unavailable after 3 attempts")

    monkeypatch.setattr("sec_filings.routes.filings.ingest_ticker", _fail)

    response = client.post(
        "/api/v1/filings/ingest",
        json={"ticker": "AAPL", "form_types": ["10-K"], "limit": 1},
    )

    assert response.status_code == 503
    assert "remained unavailable" in response.json()["error"]
