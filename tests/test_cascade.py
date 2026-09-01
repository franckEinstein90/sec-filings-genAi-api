from datetime import date

from sqlalchemy import delete, func, select

from sec_filings.db.models import Company, Filing, FilingChunk
from sec_filings.embeddings.hash_embedder import HashEmbedder


def _count(db_session, model, criterion):
    return db_session.execute(
        select(func.count()).select_from(model).where(criterion)
    ).scalar_one()


def test_database_cascade_deletes_chunks_when_filing_is_deleted(db_session):
    embedder = HashEmbedder()
    company = Company(cik="0000001201", ticker="CASFILE", name="Cascade Filing Corp")
    db_session.add(company)
    db_session.flush()
    filing = Filing(
        company_id=company.id,
        accession_number="CASCADE-FILING-2026",
        form_type="10-K",
        filing_date=date(2026, 8, 2),
        processing_status="ready",
        chunk_count=1,
        source="edgar",
    )
    db_session.add(filing)
    db_session.flush()
    chunk = FilingChunk(
        filing_id=filing.id,
        chunk_index=0,
        content="A filing chunk that must be deleted with its filing.",
        section="Item 1A Risk Factors",
        embedding=embedder.embed_query("A filing chunk that must be deleted with its filing."),
    )
    db_session.add(chunk)
    db_session.commit()
    filing_id = filing.id
    chunk_id = chunk.id

    db_session.execute(delete(Filing).where(Filing.id == filing_id))
    db_session.commit()

    assert _count(db_session, Filing, Filing.id == filing_id) == 0
    assert _count(db_session, FilingChunk, FilingChunk.id == chunk_id) == 0


def test_database_cascade_deletes_filings_and_chunks_when_company_is_deleted(db_session):
    embedder = HashEmbedder()
    company = Company(cik="0000001202", ticker="CASCOMP", name="Cascade Company Corp")
    db_session.add(company)
    db_session.flush()
    filing = Filing(
        company_id=company.id,
        accession_number="CASCADE-COMPANY-2026",
        form_type="10-Q",
        processing_status="ready",
        chunk_count=1,
        source="edgar",
    )
    db_session.add(filing)
    db_session.flush()
    chunk = FilingChunk(
        filing_id=filing.id,
        chunk_index=0,
        content="Cascade through company to filing chunk.",
        section="Item 2 MD&A",
        embedding=embedder.embed_query("Cascade through company to filing chunk."),
    )
    db_session.add(chunk)
    db_session.commit()
    company_id, filing_id, chunk_id = company.id, filing.id, chunk.id

    db_session.execute(delete(Company).where(Company.id == company_id))
    db_session.commit()

    assert _count(db_session, Company, Company.id == company_id) == 0
    assert _count(db_session, Filing, Filing.id == filing_id) == 0
    assert _count(db_session, FilingChunk, FilingChunk.id == chunk_id) == 0
