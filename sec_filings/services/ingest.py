"""Ingest SEC filings from EDGAR or uploaded files into pgvector."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date

from sec_filings.config import DEFAULT_FORM_TYPES, INGEST_DEFAULT_LIMIT
from sec_filings.db.models import Company, Filing, FilingChunk
from sec_filings.db.session import get_session
from sec_filings.edgar.client import CompanyRef, EdgarClient, EdgarError, FilingRef
from sec_filings.edgar.extract import extract_text
from sec_filings.embeddings import get_embedder
from sec_filings.rag.chunking import chunk_filing_text

logger = logging.getLogger(__name__)


def upsert_company_from_ticker(ticker: str, client: EdgarClient | None = None) -> Company:
    owns_client = client is None
    client = client or EdgarClient()
    try:
        ref = client.lookup_ticker(ticker)
        profile = {}
        try:
            profile = client.company_profile(ref.cik)
        except EdgarError as exc:
            logger.warning("Could not load submissions profile for %s: %s", ticker, exc)
        return upsert_company(ref, profile)
    finally:
        if owns_client:
            client.close()


def upsert_company(ref: CompanyRef, profile: dict | None = None) -> Company:
    profile = profile or {}
    session = get_session()
    try:
        company = session.query(Company).filter_by(cik=ref.cik).one_or_none()
        if company is None:
            company = Company(cik=ref.cik, ticker=ref.ticker, name=ref.name)
            session.add(company)
        company.ticker = ref.ticker or company.ticker
        company.name = profile.get("name") or ref.name
        company.sic = profile.get("sic")
        company.sic_description = profile.get("sic_description")
        company.exchanges = profile.get("exchanges")
        session.commit()
        session.refresh(company)
        session.expunge(company)
        return company
    finally:
        session.close()


def ingest_ticker(
    ticker: str,
    form_types: list[str] | None = None,
    limit: int | None = None,
    client: EdgarClient | None = None,
) -> dict:
    owns_client = client is None
    client = client or EdgarClient()
    forms = [form.upper() for form in (form_types or DEFAULT_FORM_TYPES)]
    cap = limit if limit is not None else INGEST_DEFAULT_LIMIT
    try:
        company = upsert_company_from_ticker(ticker, client=client)
        filings = client.list_filings(company.cik, form_types=forms, limit=cap)
        ingested = []
        skipped = []
        for filing_ref in filings:
            result = ingest_filing_ref(company.id, filing_ref, client=client)
            if result.get("skipped"):
                skipped.append(result)
            else:
                ingested.append(result)
        return {
            "company": company.to_dict(),
            "requested": cap,
            "ingested": ingested,
            "skipped": skipped,
        }
    finally:
        if owns_client:
            client.close()


def ingest_filing_ref(company_id: int, filing_ref: FilingRef, client: EdgarClient) -> dict:
    session = get_session()
    try:
        existing = (
            session.query(Filing)
            .filter_by(accession_number=filing_ref.accession_number)
            .one_or_none()
        )
        if existing and existing.processing_status == "ready":
            return {
                "skipped": True,
                "reason": "already_ingested",
                "filing": existing.to_dict(),
            }

        filing = existing or Filing(
            company_id=company_id,
            accession_number=filing_ref.accession_number,
            form_type=filing_ref.form_type,
            filing_date=filing_ref.filing_date,
            report_date=filing_ref.report_date,
            primary_document=filing_ref.primary_document,
            source="edgar",
            edgar_url=filing_ref.document_url,
            title=f"{filing_ref.form_type} {filing_ref.filing_date or ''}".strip(),
            processing_status="processing",
        )
        if existing:
            filing.processing_status = "processing"
            filing.processing_error = None
        else:
            session.add(filing)
        session.commit()
        session.refresh(filing)
        filing_id = filing.id
    finally:
        session.close()

    try:
        payload = client.download_document(filing_ref)
        text = extract_text(payload, filename=filing_ref.primary_document)
        return _index_text(
            filing_id,
            text,
            title=f"{filing_ref.form_type} {filing_ref.filing_date or ''}".strip(),
        )
    except Exception as exc:
        _mark_failed(filing_id, str(exc))
        raise


def ingest_upload(
    *,
    ticker: str,
    filename: str,
    payload: bytes,
    form_type: str = "UPLOAD",
    content_type: str | None = None,
    filing_date: date | None = None,
) -> dict:
    company = upsert_company_from_ticker(ticker)
    accession = f"UPLOAD-{uuid.uuid4().hex[:16]}"
    session = get_session()
    try:
        filing = Filing(
            company_id=company.id,
            accession_number=accession,
            form_type=(form_type or "UPLOAD").upper(),
            filing_date=filing_date,
            source="upload",
            title=filename,
            processing_status="processing",
            content_hash=hashlib.sha256(payload).hexdigest(),
        )
        session.add(filing)
        session.commit()
        session.refresh(filing)
        filing_id = filing.id
    finally:
        session.close()

    try:
        text = extract_text(payload, filename=filename, content_type=content_type)
        result = _index_text(filing_id, text, title=filename)
        result["company"] = company.to_dict()
        return result
    except Exception as exc:
        _mark_failed(filing_id, str(exc))
        raise


def _index_text(filing_id: int, text: str, title: str | None = None) -> dict:
    if not text.strip():
        raise RuntimeError("No extractable text in filing document")

    chunks = chunk_filing_text(text)
    embedder = get_embedder()
    vectors = embedder.embed_texts([chunk.content for chunk in chunks])

    session = get_session()
    try:
        filing = session.get(Filing, filing_id)
        session.query(FilingChunk).filter_by(filing_id=filing_id).delete()
        for chunk, vector in zip(chunks, vectors):
            session.add(
                FilingChunk(
                    filing_id=filing_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    section=chunk.section,
                    token_count=len(chunk.content.split()),
                    embedding=vector,
                )
            )
        filing.processing_status = "ready"
        filing.processing_error = None
        filing.chunk_count = len(chunks)
        filing.embedding_model = embedder.model_name
        if title:
            filing.title = title
        if not filing.description:
            filing.description = text[:400]
        session.commit()
        session.refresh(filing)
        return {"skipped": False, "filing": filing.to_dict()}
    finally:
        session.close()


def _mark_failed(filing_id: int, error: str) -> None:
    session = get_session()
    try:
        filing = session.get(Filing, filing_id)
        if filing is None:
            return
        filing.processing_status = "failed"
        filing.processing_error = error[:4000]
        session.commit()
    finally:
        session.close()
