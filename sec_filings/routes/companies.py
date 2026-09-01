from fastapi import APIRouter, HTTPException, Query

from sec_filings.db.models import Company, Filing
from sec_filings.db.session import get_session
from sec_filings.edgar.client import EdgarError
from sec_filings.schemas import CompanyCreate
from sec_filings.services.ingest import upsert_company_from_ticker

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


@router.get("")
def list_companies(q: str = Query(default="")):
    query = q.strip()
    session = get_session()
    try:
        stmt = session.query(Company).order_by(Company.ticker)
        if query:
            like = f"%{query}%"
            stmt = stmt.filter(
                (Company.ticker.ilike(like))
                | (Company.name.ilike(like))
                | (Company.cik.ilike(like))
            )
        companies = stmt.all()
        return {"companies": [company.to_dict() for company in companies]}
    finally:
        session.close()


@router.get("/{cik}")
def get_company(cik: str):
    session = get_session()
    try:
        company = session.query(Company).filter_by(cik=str(cik).zfill(10)).one_or_none()
        if company is None:
            company = session.query(Company).filter_by(ticker=cik.upper()).one_or_none()
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        filings = (
            session.query(Filing)
            .filter_by(company_id=company.id)
            .order_by(Filing.filing_date.desc())
            .all()
        )
        payload = company.to_dict()
        payload["filings"] = [filing.to_dict() for filing in filings]
        return {"company": payload}
    finally:
        session.close()


@router.post("", status_code=201)
def create_company(body: CompanyCreate):
    ticker = body.ticker.strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    try:
        company = upsert_company_from_ticker(ticker)
    except EdgarError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"company": company.to_dict()}
