"""ADK FunctionTools wrapping the SEC filings ingest/query stack."""

from __future__ import annotations

import json
from typing import Any

from google.adk.tools.function_tool import FunctionTool

from sec_filings.config import DEFAULT_FORM_TYPES, INGEST_DEFAULT_LIMIT, RAG_TOP_K
from sec_filings.db.models import Company, Filing, Holding
from sec_filings.db.session import get_session
from sec_filings.rag.query import query_filings
from sec_filings.services.ingest import ingest_ticker, upsert_company_from_ticker
from sec_filings.services.portfolio import DEFAULT_PORTFOLIO, get_or_create_default_portfolio


def resolve_company(ticker: str) -> dict[str, Any]:
    """Look up an SEC issuer by ticker on EDGAR and store it in the local database."""
    company = upsert_company_from_ticker(ticker)
    return company.to_dict()


def ingest_sec_filings(
    ticker: str,
    form_types: str = "10-K,10-Q,8-K",
    limit: int = INGEST_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Download recent EDGAR filings for a ticker, chunk them, embed them, and store vectors in Postgres."""
    forms = [part.strip().upper() for part in form_types.split(",") if part.strip()] or list(
        DEFAULT_FORM_TYPES
    )
    return ingest_ticker(ticker, form_types=forms, limit=int(limit))


def list_indexed_filings(ticker: str = "", form_type: str = "") -> dict[str, Any]:
    """List SEC filings already ingested into the local pgvector database."""
    session = get_session()
    try:
        stmt = session.query(Filing).join(Company)
        if ticker.strip():
            stmt = stmt.filter(Company.ticker == ticker.strip().upper())
        if form_type.strip():
            stmt = stmt.filter(Filing.form_type == form_type.strip().upper())
        filings = stmt.order_by(Filing.filing_date.desc(), Filing.id.desc()).all()
        return {"filings": [filing.to_dict(include_company=True) for filing in filings]}
    finally:
        session.close()


def query_sec_filings(
    prompt: str,
    ticker: str = "",
    form_type: str = "",
    top_k: int = RAG_TOP_K,
) -> dict[str, Any]:
    """Answer a question about ingested SEC filings using pgvector similarity search and RAG."""
    return query_filings(
        prompt,
        ticker=ticker.strip().upper() or None,
        form_type=form_type.strip().upper() or None,
        top_k=int(top_k),
    )


def add_watchlist_holding(ticker: str, shares: float = 0.0) -> dict[str, Any]:
    """Add a ticker to the default Watchlist portfolio, creating the issuer record if needed."""
    company = upsert_company_from_ticker(ticker)
    session = get_session()
    try:
        portfolio = get_or_create_default_portfolio(session)
        existing = (
            session.query(Holding)
            .filter_by(portfolio_id=portfolio.id, company_id=company.id)
            .one_or_none()
        )
        if existing:
            if shares:
                existing.shares = float(shares)
            session.commit()
            session.refresh(existing)
            return {"holding": existing.to_dict(), "updated": True}
        holding = Holding(
            portfolio_id=portfolio.id,
            company_id=company.id,
            ticker=company.ticker or ticker.upper(),
            shares=float(shares) if shares else None,
        )
        session.add(holding)
        session.commit()
        session.refresh(holding)
        return {"holding": holding.to_dict(), "updated": False}
    finally:
        session.close()


def list_watchlist() -> dict[str, Any]:
    """Return holdings on the default Watchlist portfolio."""
    session = get_session()
    try:
        portfolio = get_or_create_default_portfolio(session)
        session.refresh(portfolio)
        return {
            "portfolio": portfolio.to_dict(include_holdings=True),
            "holdings": [holding.to_dict() for holding in portfolio.holdings],
        }
    finally:
        session.close()


ADK_TOOLS: list[FunctionTool] = [
    FunctionTool(resolve_company),
    FunctionTool(ingest_sec_filings),
    FunctionTool(list_indexed_filings),
    FunctionTool(query_sec_filings),
    FunctionTool(add_watchlist_holding),
    FunctionTool(list_watchlist),
]


def tools_by_name() -> dict[str, FunctionTool]:
    return {tool.name: tool for tool in ADK_TOOLS}


def dump_tool_result(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)
