from datetime import date

from sec_filings.db.models import Company, Filing, FilingChunk
from sec_filings.embeddings.hash_embedder import HashEmbedder
from sec_filings.rag.query import query_filings


class RecordingLLM:
    def __init__(self):
        self.prompt = None
        self.system_prompt = None

    def complete(self, prompt: str, system_prompt: str):
        self.prompt = prompt
        self.system_prompt = system_prompt
        return {
            "content": "Grounded answer from the supplied filing excerpts.",
            "model": "recording",
            "usage": {"input_tokens": 10, "output_tokens": 8},
        }


def _seed_citation_filing(db_session):
    embedder = HashEmbedder()
    company = Company(cik="0000001401", ticker="CITEVAL", name="Citation Evaluation Corp")
    db_session.add(company)
    db_session.flush()
    filing = Filing(
        company_id=company.id,
        accession_number="CITATION-EVAL-2026",
        form_type="10-K",
        filing_date=date(2026, 8, 4),
        processing_status="ready",
        chunk_count=2,
        embedding_model=embedder.model_name,
        source="edgar",
        edgar_url="https://sec.example/citation-eval",
    )
    db_session.add(filing)
    db_session.flush()
    chunks = [
        (
            "The company depends on a limited number of semiconductor suppliers.",
            "Item 1A Risk Factors",
        ),
        (
            "Management expects capital expenditures to rise for data center capacity.",
            "Item 7 Management's Discussion and Analysis",
        ),
    ]
    stored = []
    for index, (content, section) in enumerate(chunks):
        chunk = FilingChunk(
            filing_id=filing.id,
            chunk_index=index,
            content=content,
            section=section,
            embedding=embedder.embed_query(content),
        )
        db_session.add(chunk)
        stored.append(chunk)
    db_session.commit()
    return filing, stored


def test_rag_citations_are_grounded_ranked_and_traceable(db_session, monkeypatch):
    filing, stored_chunks = _seed_citation_filing(db_session)
    recorder = RecordingLLM()
    monkeypatch.setattr("sec_filings.rag.query.get_llm", lambda: recorder)

    result = query_filings(
        "What supply-chain risks are disclosed?",
        ticker="CITEVAL",
        form_type="10-K",
        top_k=2,
    )

    assert result["answer"].startswith("Grounded answer")
    assert result["model"] == "recording"
    assert 1 <= len(result["citations"]) <= 2

    stored_content = {chunk.content for chunk in stored_chunks}
    scores = [citation["score"] for citation in result["citations"]]
    assert scores == sorted(scores, reverse=True)

    required = {
        "chunk_id",
        "filing_id",
        "ticker",
        "cik",
        "company",
        "form_type",
        "filing_date",
        "section",
        "score",
        "excerpt",
        "edgar_url",
    }
    for rank, citation in enumerate(result["citations"], start=1):
        assert required <= set(citation)
        assert citation["filing_id"] == filing.id
        assert citation["ticker"] == "CITEVAL"
        assert citation["form_type"] == "10-K"
        assert citation["filing_date"] == "2026-08-04"
        assert 0.0 <= citation["score"] <= 1.0
        assert any(citation["excerpt"] in content for content in stored_content)
        assert f"[{rank}] CITEVAL 10-K 2026-08-04" in recorder.prompt
        assert citation["section"] in recorder.prompt


def test_no_matching_metadata_returns_no_citations_and_skips_llm(db_session, monkeypatch):
    _seed_citation_filing(db_session)

    def _should_not_be_called():
        raise AssertionError("LLM should not be created when retrieval has no hits")

    monkeypatch.setattr("sec_filings.rag.query.get_llm", _should_not_be_called)

    result = query_filings(
        "What risks are disclosed?",
        ticker="DOESNOTEXIST",
        top_k=3,
    )

    assert result["citations"] == []
    assert result["model"] is None
    assert "No indexed filings" in result["answer"]
