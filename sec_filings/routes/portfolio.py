from datetime import date

from flask import Blueprint, jsonify, request

from sec_filings.db.models import Holding, Portfolio
from sec_filings.db.session import get_session
from sec_filings.edgar.client import EdgarError
from sec_filings.services.ingest import upsert_company_from_ticker

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/api/v1")
DEFAULT_PORTFOLIO = "Watchlist"


@portfolio_bp.get("/portfolio")
def list_default_portfolio():
    session = get_session()
    try:
        portfolio = _get_or_create_default(session)
        session.refresh(portfolio)
        return jsonify(
            {
                "portfolio": portfolio.to_dict(include_holdings=True),
                "holdings": [holding.to_dict() for holding in portfolio.holdings],
            }
        )
    finally:
        session.close()


@portfolio_bp.get("/portfolios")
def list_portfolios():
    session = get_session()
    try:
        portfolios = session.query(Portfolio).order_by(Portfolio.name).all()
        return jsonify({"portfolios": [item.to_dict(include_holdings=True) for item in portfolios]})
    finally:
        session.close()


@portfolio_bp.post("/portfolios")
def create_portfolio():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    session = get_session()
    try:
        existing = session.query(Portfolio).filter_by(name=name).one_or_none()
        if existing:
            return jsonify({"error": "Portfolio already exists", "portfolio": existing.to_dict()}), 409
        portfolio = Portfolio(name=name, description=(data.get("description") or "").strip() or None)
        session.add(portfolio)
        session.commit()
        session.refresh(portfolio)
        return jsonify({"portfolio": portfolio.to_dict()}), 201
    finally:
        session.close()


@portfolio_bp.get("/portfolios/<int:portfolio_id>")
def get_portfolio(portfolio_id: int):
    session = get_session()
    try:
        portfolio = session.get(Portfolio, portfolio_id)
        if portfolio is None:
            return jsonify({"error": "Portfolio not found"}), 404
        return jsonify({"portfolio": portfolio.to_dict(include_holdings=True)})
    finally:
        session.close()


@portfolio_bp.post("/portfolios/<int:portfolio_id>/holdings")
def add_holding(portfolio_id: int):
    data = request.get_json(silent=True) or {}
    ticker = (data.get("ticker") or "").strip()
    if not ticker:
        return jsonify({"error": "ticker is required"}), 400
    session = get_session()
    try:
        portfolio = session.get(Portfolio, portfolio_id)
        if portfolio is None:
            return jsonify({"error": "Portfolio not found"}), 404
        try:
            company = upsert_company_from_ticker(ticker)
        except EdgarError as exc:
            return jsonify({"error": str(exc)}), 404
        existing = (
            session.query(Holding)
            .filter_by(portfolio_id=portfolio.id, company_id=company.id)
            .one_or_none()
        )
        as_of = _parse_date(data.get("as_of"))
        shares = data.get("shares")
        if existing:
            existing.shares = float(shares) if shares is not None else existing.shares
            existing.as_of = as_of or existing.as_of
            session.commit()
            session.refresh(existing)
            return jsonify({"holding": existing.to_dict(), "updated": True})
        holding = Holding(
            portfolio_id=portfolio.id,
            company_id=company.id,
            ticker=company.ticker or ticker.upper(),
            shares=float(shares) if shares is not None else None,
            as_of=as_of,
        )
        session.add(holding)
        session.commit()
        session.refresh(holding)
        return jsonify({"holding": holding.to_dict()}), 201
    finally:
        session.close()


@portfolio_bp.delete("/portfolios/<int:portfolio_id>/holdings/<int:holding_id>")
def delete_holding(portfolio_id: int, holding_id: int):
    session = get_session()
    try:
        holding = session.get(Holding, holding_id)
        if holding is None or holding.portfolio_id != portfolio_id:
            return jsonify({"error": "Holding not found"}), 404
        session.delete(holding)
        session.commit()
        return jsonify({"message": "Holding removed"})
    finally:
        session.close()


def _get_or_create_default(session) -> Portfolio:
    portfolio = session.query(Portfolio).filter_by(name=DEFAULT_PORTFOLIO).one_or_none()
    if portfolio is None:
        portfolio = Portfolio(name=DEFAULT_PORTFOLIO, description="Default SEC filings watchlist")
        session.add(portfolio)
        session.commit()
    return portfolio


def _parse_date(value):
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])
