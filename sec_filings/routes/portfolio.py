from datetime import date

from fastapi import APIRouter, HTTPException

from sec_filings.db.models import Holding, Portfolio
from sec_filings.db.session import get_session
from sec_filings.edgar.client import EdgarError
from sec_filings.schemas import HoldingCreate, PortfolioCreate
from sec_filings.services.ingest import upsert_company_from_ticker
from sec_filings.services.portfolio import get_or_create_default_portfolio

router = APIRouter(prefix="/api/v1", tags=["portfolio"])


@router.get("/portfolio")
def list_default_portfolio():
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


@router.get("/portfolios")
def list_portfolios():
    session = get_session()
    try:
        portfolios = session.query(Portfolio).order_by(Portfolio.name).all()
        return {"portfolios": [item.to_dict(include_holdings=True) for item in portfolios]}
    finally:
        session.close()


@router.post("/portfolios", status_code=201)
def create_portfolio(body: PortfolioCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    session = get_session()
    try:
        existing = session.query(Portfolio).filter_by(name=name).one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Portfolio already exists")
        description = (body.description or "").strip() or None
        portfolio = Portfolio(name=name, description=description)
        session.add(portfolio)
        session.commit()
        session.refresh(portfolio)
        return {"portfolio": portfolio.to_dict()}
    finally:
        session.close()


@router.get("/portfolios/{portfolio_id}")
def get_portfolio(portfolio_id: int):
    session = get_session()
    try:
        portfolio = session.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        return {"portfolio": portfolio.to_dict(include_holdings=True)}
    finally:
        session.close()


@router.post("/portfolios/{portfolio_id}/holdings", status_code=201)
def add_holding(portfolio_id: int, body: HoldingCreate):
    ticker = body.ticker.strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    session = get_session()
    try:
        portfolio = session.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        try:
            company = upsert_company_from_ticker(ticker)
        except EdgarError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        existing = (
            session.query(Holding)
            .filter_by(portfolio_id=portfolio.id, company_id=company.id)
            .one_or_none()
        )
        as_of = _parse_date(body.as_of)
        if existing:
            existing.shares = float(body.shares) if body.shares is not None else existing.shares
            existing.as_of = as_of or existing.as_of
            session.commit()
            session.refresh(existing)
            return {"holding": existing.to_dict(), "updated": True}
        holding = Holding(
            portfolio_id=portfolio.id,
            company_id=company.id,
            ticker=company.ticker or ticker.upper(),
            shares=float(body.shares) if body.shares is not None else None,
            as_of=as_of,
        )
        session.add(holding)
        session.commit()
        session.refresh(holding)
        return {"holding": holding.to_dict()}
    finally:
        session.close()


@router.delete("/portfolios/{portfolio_id}/holdings/{holding_id}")
def delete_holding(portfolio_id: int, holding_id: int):
    session = get_session()
    try:
        holding = session.get(Holding, holding_id)
        if holding is None or holding.portfolio_id != portfolio_id:
            raise HTTPException(status_code=404, detail="Holding not found")
        session.delete(holding)
        session.commit()
        return {"message": "Holding removed"}
    finally:
        session.close()


def _parse_date(value):
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])
