from __future__ import annotations

import os
from datetime import date

from sec_filings.edgar.client import CompanyRef, EdgarError, FilingRef


class FakeEdgarClient:
    """In-memory EDGAR stand-in for tests (no network)."""

    def __init__(self, documents: dict[str, bytes] | None = None):
        self.documents = documents or {}
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def lookup_ticker(self, ticker: str) -> CompanyRef:
        key = ticker.strip().upper()
        known = {
            "AAPL": CompanyRef(cik="0000320193", ticker="AAPL", name="Apple Inc."),
            "MSFT": CompanyRef(cik="0000789019", ticker="MSFT", name="MICROSOFT CORP"),
        }
        if key not in known:
            raise EdgarError(f"Ticker not found on EDGAR: {ticker}")
        return known[key]

    def company_profile(self, cik: str) -> dict:
        padded = str(cik).zfill(10)
        if padded == "0000320193":
            return {
                "cik": padded,
                "name": "Apple Inc.",
                "tickers": ["AAPL"],
                "exchanges": ["Nasdaq"],
                "sic": "3571",
                "sic_description": "Electronic Computers",
            }
        if padded == "0000789019":
            return {
                "cik": padded,
                "name": "MICROSOFT CORP",
                "tickers": ["MSFT"],
                "exchanges": ["Nasdaq"],
                "sic": "7372",
                "sic_description": "Prepackaged Software",
            }
        raise EdgarError(f"Unknown CIK {cik}")

    def list_filings(self, cik: str, form_types=None, limit: int = 10):
        padded = str(cik).zfill(10)
        sample = FilingRef(
            accession_number="0000320193-24-000123",
            form_type="10-K",
            filing_date=date(2024, 11, 1),
            report_date=date(2024, 9, 28),
            primary_document="aapl-20240928.htm",
            cik=padded,
        )
        forms = {form.upper() for form in (form_types or [])}
        if forms and sample.form_type not in forms:
            return []
        return [sample][:limit]

    def download_document(self, filing: FilingRef) -> bytes:
        if filing.primary_document in self.documents:
            return self.documents[filing.primary_document]
        html = """
        <html><body>
        <p>Item 1A. Risk Factors</p>
        <p>Apple faces competition in smartphone markets and supply chain disruption risk.</p>
        <p>Item 7. Management's Discussion and Analysis</p>
        <p>iPhone revenue remained the largest contributor to net sales in fiscal 2024.</p>
        </body></html>
        """
        return html.encode("utf-8")
