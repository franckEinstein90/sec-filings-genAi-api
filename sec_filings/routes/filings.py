from flask import Blueprint, jsonify, request

from sec_filings.config import DEFAULT_FORM_TYPES, INGEST_DEFAULT_LIMIT
from sec_filings.db.models import Company, Filing
from sec_filings.db.session import get_session
from sec_filings.edgar.client import EdgarError
from sec_filings.services.ingest import ingest_ticker, ingest_upload

filings_bp = Blueprint("filings", __name__, url_prefix="/api/v1/filings")


@filings_bp.get("")
def list_filings():
    ticker = (request.args.get("ticker") or "").strip().upper() or None
    cik = (request.args.get("cik") or "").strip() or None
    form_type = (request.args.get("form_type") or "").strip().upper() or None
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
        return jsonify({"filings": [filing.to_dict(include_company=True) for filing in filings]})
    finally:
        session.close()


@filings_bp.get("/<int:filing_id>")
def get_filing(filing_id: int):
    session = get_session()
    try:
        filing = session.get(Filing, filing_id)
        if filing is None:
            return jsonify({"error": "Filing not found"}), 404
        return jsonify({"filing": filing.to_dict(include_company=True)})
    finally:
        session.close()


@filings_bp.delete("/<int:filing_id>")
def delete_filing(filing_id: int):
    session = get_session()
    try:
        filing = session.get(Filing, filing_id)
        if filing is None:
            return jsonify({"error": "Filing not found"}), 404
        session.delete(filing)
        session.commit()
        return jsonify({"message": "Filing deleted"})
    finally:
        session.close()


@filings_bp.post("/ingest")
def ingest_from_edgar():
    data = request.get_json(silent=True) or {}
    ticker = (data.get("ticker") or "").strip()
    if not ticker:
        return jsonify({"error": "ticker is required"}), 400
    form_types = data.get("form_types") or list(DEFAULT_FORM_TYPES)
    limit = data.get("limit", INGEST_DEFAULT_LIMIT)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400
    try:
        result = ingest_ticker(ticker, form_types=form_types, limit=limit)
    except EdgarError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify(result), 201


@filings_bp.post("/upload")
def upload_filing():
    file = request.files.get("file")
    ticker = (request.form.get("ticker") or "").strip()
    form_type = (request.form.get("form_type") or "UPLOAD").strip()
    if not file or not file.filename:
        return jsonify({"error": "file is required"}), 400
    if not ticker:
        return jsonify({"error": "ticker is required"}), 400
    payload = file.read()
    if not payload:
        return jsonify({"error": "empty file"}), 400
    try:
        result = ingest_upload(
            ticker=ticker,
            filename=file.filename,
            payload=payload,
            form_type=form_type,
            content_type=file.mimetype,
        )
    except EdgarError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result), 201
