from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from sec_filings.config import DEFAULT_FORM_TYPES, INGEST_DEFAULT_LIMIT
from sec_filings.db.models import Company, Filing
from sec_filings.db.session import get_session
from sec_filings.edgar.client import EdgarError
from sec_filings.schemas import IngestRequest
from sec_filings.services.ingest import ingest_ticker, ingest_upload

router = APIRouter(prefix="/api/v1/filings", tags=["filings"])


@router.get("")
def list_filings(
    ticker: str | None = Query(default=None),
    cik: str | None = Query(default=None),
    form_type: str | None = Query(default=None),
):
    ticker = (ticker or "").strip().upper() or None
    cik = (cik or "").strip() or None
    form_type = (form_type or "").strip().upper() or None
    session = get_session()
    try:
        stmt = session.query(Filing).join(Company)
        if ticker:
            stmt = stmt.filter(Company.ticker == ticker)
        if cik:
            stmt = stmt.filter(Company.cik == cik.zfill(10))
        if form_type:
            stmt = stmt.filter(Filing.form_type == form_type)
        filings = stmt.order_by(Filing.filing_date.desc(), Filing.id.desc()).all()
        return {"filings": [filing.to_dict(include_company=True) for filing in filings]}
    finally:
        session.close()


@router.get("/{filing_id}")
def get_filing(filing_id: int):
    session = get_session()
    try:
        filing = session.get(Filing, filing_id)
        if filing is None:
            raise HTTPException(status_code=404, detail="Filing not found")
        return {"filing": filing.to_dict(include_company=True)}
    finally:
        session.close()


@router.delete("/{filing_id}")
def delete_filing(filing_id: int):
    session = get_session()
    try:
        filing = session.get(Filing, filing_id)
        if filing is None:
            raise HTTPException(status_code=404, detail="Filing not found")
        session.delete(filing)
        session.commit()
        return {"message": "Filing deleted"}
    finally:
        session.close()


@router.post("/ingest", status_code=201)
def ingest_from_edgar(body: IngestRequest):
    ticker = body.ticker.strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    form_types = body.form_types or list(DEFAULT_FORM_TYPES)
    limit = body.limit if body.limit is not None else INGEST_DEFAULT_LIMIT
    try:
        result = ingest_ticker(ticker, form_types=form_types, limit=limit)
    except EdgarError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return result


@router.post("/upload", status_code=201)
async def upload_filing(
    file: UploadFile = File(...),
    ticker: str = Form(...),
    form_type: str = Form("UPLOAD"),
):
    ticker = ticker.strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    if not file.filename:
        raise HTTPException(status_code=400, detail="file is required")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="empty file")
    try:
        result = ingest_upload(
            ticker=ticker,
            filename=file.filename,
            payload=payload,
            form_type=form_type.strip() or "UPLOAD",
            content_type=file.content_type,
        )
    except EdgarError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result
