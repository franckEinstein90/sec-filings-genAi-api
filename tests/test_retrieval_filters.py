from datetime import date

from sec_filings.db.models import Company, Filing, FilingChunk
from sec_filings.embeddings.hash_embedder import HashEmbedder
from sec_filings.rag.query import _similarity_search


def _add_filing(db_session, *, cik, ticker, form_type, accession, text, section):
    embedder = HashEmbedder()
    company = Company(cik=cik, ticker=ticker, name=f"{ticker} Corp")
    db_session.add(company)
    db_session.flush()
    filing = Filing(
        company_id=company.id,
        accession_number=accession,
        form_type=form_type,
        filing_date=date(2026, 8, 1),
        processing_status="ready",
        chunk_count=1,
        embedding_model=embedder.model_name,
        source="edgar",
        edgar_url=f"https://sec.example/{accession}",
    )
    db_session.add(filing)
    db_session.flush()
    db_session.add(
        FilingChunk(
            filing_id=filing.id,
            chunk_index=0,
            content=text,
            section=section,
            embedding=embedder.embed_query(text),
        )
    )
    db_session.commit()
    return filing


def test_similarity_search_respects_ticker_form_and_filing_metadata_filters(db_session):
    first = _add_filing(
        db_session,
        cik="0000001101",
        ticker="FLTONE",
        form_type="10-K",
        accession="FILTER-ONE-2026",
        text="Artificial intelligence data center concentration creates supplier risk.",
        section="Item 1A Risk Factors",
    )
    second = _add_filing(
        db_session,
        cik="0000001102",
        ticker="FLTTWO",
        form_type="10-Q",
        accession="FILTER-TWO-2026",
        text="Artificial intelligence data center demand improved quarterly revenue.",
        section="Item 2 MD&A",
    )
    embedder = HashEmbedder()
    query_vector = embedder.embed_query("artificial intelligence data center risk")

    ticker_hits = _similarity_search(
        db_session,
        query_vector,
        ticker="FLTONE",
        cik=None,
        filing_id=None,
        form_type=None,
        top_k=10,
    )
    assert ticker_hits
    assert {hit["ticker"] for hit in ticker_hits} == {"FLTONE"}
    assert {hit["filing_id"] for hit in ticker_hits} == {first.id}

    form_hits = _similarity_search(
        db_session,
        query_vector,
        ticker="FLTTWO",
        cik=None,
        filing_id=None,
        form_type="10-Q",
        top_k=10,
    )
    assert form_hits
    assert {hit["ticker"] for hit in form_hits} == {"FLTTWO"}
    assert {hit["filing_id"] for hit in form_hits} == {second.id}

    wrong_form_hits = _similarity_search(
        db_session,
        query_vector,
        ticker="FLTTWO",
        cik=None,
        filing_id=None,
        form_type="10-K",
        top_k=10,
    )
    assert wrong_form_hits == []

    filing_hits = _similarity_search(
        db_session,
        query_vector,
        ticker=None,
        cik=None,
        filing_id=first.id,
        form_type=None,
        top_k=10,
    )
    assert filing_hits
    assert {hit["filing_id"] for hit in filing_hits} == {first.id}


def test_similarity_search_honors_top_k_after_filtering(db_session):
    filing = _add_filing(
        db_session,
        cik="0000001103",
        ticker="FLTLIM",
        form_type="10-K",
        accession="FILTER-LIMIT-2026",
        text="Cybersecurity risk affects operations.",
        section="Item 1A Risk Factors",
    )
    embedder = HashEmbedder()
    second_text = "Cybersecurity incidents may interrupt operations and revenue."
    db_session.add(
        FilingChunk(
            filing_id=filing.id,
            chunk_index=1,
            content=second_text,
            section="Item 1A Risk Factors",
            embedding=embedder.embed_query(second_text),
        )
    )
    filing.chunk_count = 2
    db_session.commit()

    hits = _similarity_search(
        db_session,
        embedder.embed_query("cybersecurity operations risk"),
        ticker="FLTLIM",
        cik=None,
        filing_id=None,
        form_type="10-K",
        top_k=1,
    )

    assert len(hits) == 1
    assert hits[0]["ticker"] == "FLTLIM"
