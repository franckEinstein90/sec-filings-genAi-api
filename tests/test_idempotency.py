from sec_filings.db.models import Filing, FilingChunk
from sec_filings.services.ingest import ingest_ticker, ingest_upload


def test_edgar_ingestion_is_idempotent(fake_edgar, db_session):
    first = ingest_ticker("AAPL", form_types=["10-K"], limit=1, client=fake_edgar)
    first_record = (first["ingested"] or first["skipped"])[0]["filing"]
    filing_id = first_record["id"]

    filing_count = db_session.query(Filing).filter_by(accession_number=first_record["accession_number"]).count()
    chunk_count = db_session.query(FilingChunk).filter_by(filing_id=filing_id).count()

    second = ingest_ticker("AAPL", form_types=["10-K"], limit=1, client=fake_edgar)

    assert second["ingested"] == []
    assert len(second["skipped"]) == 1
    assert second["skipped"][0]["reason"] == "already_ingested"
    assert second["skipped"][0]["filing"]["id"] == filing_id
    assert db_session.query(Filing).filter_by(accession_number=first_record["accession_number"]).count() == filing_count
    assert db_session.query(FilingChunk).filter_by(filing_id=filing_id).count() == chunk_count


def test_identical_upload_is_deduplicated_by_content_hash(fake_edgar, db_session):
    payload = b"Item 1A. Risk Factors\nTEST-IDEMPOTENCY unique liquidity risk disclosure."

    first = ingest_upload(
        ticker="MSFT",
        filename="first-idempotency.txt",
        payload=payload,
        form_type="8-K",
        content_type="text/plain",
    )
    second = ingest_upload(
        ticker="MSFT",
        filename="second-idempotency.txt",
        payload=payload,
        form_type="8-K",
        content_type="text/plain",
    )

    assert first["skipped"] is False
    assert second["skipped"] is True
    assert second["reason"] == "duplicate_content"
    assert second["filing"]["id"] == first["filing"]["id"]

    content_hash = (
        db_session.query(Filing.content_hash)
        .filter(Filing.id == first["filing"]["id"])
        .scalar()
    )
    assert db_session.query(Filing).filter_by(
        company_id=first["filing"]["company_id"],
        source="upload",
        content_hash=content_hash,
    ).count() == 1
