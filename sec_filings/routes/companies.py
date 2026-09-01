from flask import Blueprint, jsonify, request

from sec_filings.db.models import Company, Filing
from sec_filings.db.session import get_session
from sec_filings.edgar.client import EdgarError
from sec_filings.services.ingest import upsert_company_from_ticker

companies_bp = Blueprint("companies", __name__, url_prefix="/api/v1/companies")


@companies_bp.get("")
def list_companies():
    query = (request.args.get("q") or "").strip()
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
        return jsonify({"companies": [company.to_dict() for company in companies]})
    finally:
        session.close()


@companies_bp.get("/<cik>")
def get_company(cik: str):
    session = get_session()
    try:
        company = session.query(Company).filter_by(cik=str(cik).zfill(10)).one_or_none()
        if company is None:
            company = session.query(Company).filter_by(ticker=cik.upper()).one_or_none()
        if company is None:
            return jsonify({"error": "Company not found"}), 404
        filings = (
            session.query(Filing)
            .filter_by(company_id=company.id)
            .order_by(Filing.filing_date.desc())
            .all()
        )
        payload = company.to_dict()
        payload["filings"] = [filing.to_dict() for filing in filings]
        return jsonify({"company": payload})
    finally:
        session.close()


@companies_bp.post("")
def create_company():
    data = request.get_json(silent=True) or {}
    ticker = (data.get("ticker") or "").strip()
    if not ticker:
        return jsonify({"error": "ticker is required"}), 400
    try:
        company = upsert_company_from_ticker(ticker)
    except EdgarError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"company": company.to_dict()}), 201
