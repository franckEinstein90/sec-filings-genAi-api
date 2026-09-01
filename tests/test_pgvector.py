from sqlalchemy import text

from sec_filings.db.bootstrap import get_engine
from sec_filings.db.models import Company, Filing, FilingChunk
from sec_filings.embeddings.hash_embedder import HashEmbedder


def test_pgvector_extension_is_installed(app):
    engine = get_engine()
    with engine.connect() as conn:
        version = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
    assert version


def test_similarity_search_returns_nearest_chunk(db_session):
    embedder = HashEmbedder()
    company = Company(cik="0000000001", ticker="TEST", name="Test Issuer")
    db_session.add(company)
    db_session.flush()
    filing = Filing(
        company_id=company.id,
        accession_number="TEST-0001",
        form_type="10-K",
        processing_status="ready",
        chunk_count=2,
        embedding_model=embedder.model_name,
        source="upload",
    )
    db_session.add(filing)
    db_session.flush()

    target = "artificial intelligence model risk in data centers"
    other = "unrelated discussion of office leases in nebraska"
    db_session.add(
        FilingChunk(
            filing_id=filing.id,
            chunk_index=0,
            content=target,
            section="Item 1A Risk Factors",
            embedding=embedder.embed_query(target),
        )
    )
    db_session.add(
        FilingChunk(
            filing_id=filing.id,
            chunk_index=1,
            content=other,
            section="Item 2 Properties",
            embedding=embedder.embed_query(other),
        )
    )
    db_session.commit()

    query_vector = embedder.embed_query(target)
    distance = FilingChunk.embedding.cosine_distance(query_vector)
    rows = (
        db_session.query(FilingChunk.content, distance.label("distance"))
        .order_by(distance)
        .limit(2)
        .all()
    )
    assert rows[0].content == target
    assert rows[0].distance < rows[1].distance
