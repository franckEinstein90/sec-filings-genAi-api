"""EDGAR HTTP client (company tickers, submissions, filing documents)."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import httpx

from sec_filings.config import (
    MAX_DOWNLOAD_BYTES,
    SEC_ARCHIVES_BASE,
    SEC_SUBMISSIONS_URL,
    SEC_TICKERS_URL,
    SEC_USER_AGENT,
)

logger = logging.getLogger(__name__)

_TICKER_CACHE: dict[str, "CompanyRef"] | None = None


class EdgarError(RuntimeError):
    pass


class EdgarTransientError(EdgarError):
    """Raised when EDGAR remains rate limited or temporarily unavailable."""


@dataclass(frozen=True)
class CompanyRef:
    cik: str
    ticker: str
    name: str


@dataclass(frozen=True)
class FilingRef:
    accession_number: str
    form_type: str
    filing_date: date | None
    report_date: date | None
    primary_document: str
    cik: str

    @property
    def accession_nodash(self) -> str:
        return self.accession_number.replace("-", "")

    @property
    def document_url(self) -> str:
        cik_int = str(int(self.cik))
        return (
            f"{SEC_ARCHIVES_BASE}/{cik_int}/{self.accession_nodash}/{self.primary_document}"
        )


class EdgarClient:
    def __init__(
        self,
        user_agent: str = SEC_USER_AGENT,
        timeout: float = 30.0,
        min_interval: float = 0.15,
        max_retries: int = 2,
        retry_backoff: float = 0.5,
        client: httpx.Client | None = None,
    ):
        self.user_agent = user_agent
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
            },
            follow_redirects=True,
        )
        self.min_interval = min_interval
        self.max_retries = max(0, max_retries)
        self.retry_backoff = max(0.0, retry_backoff)
        self._last_request = 0.0

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "EdgarClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def lookup_ticker(self, ticker: str) -> CompanyRef:
        key = ticker.strip().upper()
        mapping = self._ticker_map()
        if key not in mapping:
            raise EdgarError(f"Ticker not found on EDGAR: {ticker}")
        return mapping[key]

    def get_submissions(self, cik: str) -> dict[str, Any]:
        padded = _pad_cik(cik)
        url = SEC_SUBMISSIONS_URL.format(cik=padded)
        response = self._get(url)
        return response.json()

    def list_filings(
        self,
        cik: str,
        form_types: Iterable[str] | None = None,
        limit: int = 10,
    ) -> list[FilingRef]:
        payload = self.get_submissions(cik)
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        documents = recent.get("primaryDocument", [])
        wanted = {form.upper() for form in (form_types or [])}

        results: list[FilingRef] = []
        for index, form in enumerate(forms):
            if wanted and str(form).upper() not in wanted:
                continue
            accession = accessions[index]
            primary = documents[index] if index < len(documents) else ""
            if not primary:
                continue
            results.append(
                FilingRef(
                    accession_number=accession,
                    form_type=str(form),
                    filing_date=_parse_date(filing_dates[index] if index < len(filing_dates) else None),
                    report_date=_parse_date(report_dates[index] if index < len(report_dates) else None),
                    primary_document=primary,
                    cik=_pad_cik(cik),
                )
            )
            if len(results) >= limit:
                break
        return results

    def company_profile(self, cik: str) -> dict[str, Any]:
        payload = self.get_submissions(cik)
        return {
            "cik": _pad_cik(payload.get("cik", cik)),
            "name": payload.get("name"),
            "tickers": payload.get("tickers") or [],
            "exchanges": payload.get("exchanges") or [],
            "sic": str(payload.get("sic") or "") or None,
            "sic_description": payload.get("sicDescription"),
        }

    def download_document(self, filing: FilingRef) -> bytes:
        response = self._get(filing.document_url)
        content = response.content
        if len(content) > MAX_DOWNLOAD_BYTES:
            raise EdgarError(
                f"Filing document exceeds MAX_DOWNLOAD_BYTES ({MAX_DOWNLOAD_BYTES})"
            )
        return content

    def _ticker_map(self) -> dict[str, CompanyRef]:
        global _TICKER_CACHE
        if _TICKER_CACHE is not None:
            return _TICKER_CACHE
        response = self._get(SEC_TICKERS_URL)
        data = response.json()
        mapping: dict[str, CompanyRef] = {}
        for row in data.values():
            ticker = str(row.get("ticker", "")).upper()
            if not ticker:
                continue
            mapping[ticker] = CompanyRef(
                cik=_pad_cik(row.get("cik_str")),
                ticker=ticker,
                name=str(row.get("title") or ticker),
            )
        _TICKER_CACHE = mapping
        return mapping

    def _get(self, url: str) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            self._throttle()
            logger.debug("EDGAR GET %s", url)
            response = self._client.get(url)

            if response.status_code in {429, 503}:
                if attempt >= self.max_retries:
                    raise EdgarTransientError(
                        f"EDGAR remained unavailable after {attempt + 1} attempts "
                        f"(HTTP {response.status_code}): {url}"
                    )
                delay = self._retry_delay(response, attempt)
                logger.warning(
                    "EDGAR returned %s; retrying in %.2fs (%s/%s)",
                    response.status_code,
                    delay,
                    attempt + 1,
                    self.max_retries,
                )
                if delay:
                    time.sleep(delay)
                continue

            if response.status_code == 403:
                raise EdgarError(
                    "EDGAR returned 403. Set SEC_USER_AGENT to a descriptive string "
                    "that includes a contact email, as required by the SEC."
                )
            if response.status_code >= 400:
                raise EdgarError(f"EDGAR request failed ({response.status_code}): {url}")
            return response

        raise EdgarTransientError(f"EDGAR request failed after retries: {url}")

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, min(float(retry_after), 30.0))
            except ValueError:
                pass
        return min(self.retry_backoff * (2**attempt), 30.0)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request = time.monotonic()


def _pad_cik(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        raise EdgarError(f"Invalid CIK: {value!r}")
    return digits.zfill(10)


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def reset_ticker_cache() -> None:
    global _TICKER_CACHE
    _TICKER_CACHE = None
