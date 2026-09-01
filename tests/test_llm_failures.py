from datetime import date

import pytest

from sec_filings.db.models import Company, Filing, FilingChunk
from sec_filings.embeddings.hash_embedder import HashEmbedder
from sec_filings.rag.llm import LLMError, OpenAILLM, get_llm


class FailingLLM:
    def complete(self, prompt: str, system_prompt: str):
        raise LLMError("simulated upstream LLM outage")


class _ExplodingCompletions:
    def create(self, **_kwargs):
        raise ConnectionError("provider socket closed")


class _ExplodingChat:
    completions = _ExplodingCompletions()


class _ExplodingOpenAIClient:
    chat = _ExplodingChat()


def _seed_queryable_filing(db_session):
    embedder = HashEmbedder()
    company = Company(cik="0000001301", ticker="LLMFAIL", name="LLM Failure Corp")
    db_session.add(company)
    db_session.flush()
    filing = Filing(
        company_id=company.id,
        accession_number="LLM-FAILURE-2026",
        form_type="10-K",
        filing_date=date(2026, 8, 3),
        processing_status="ready",
        chunk_count=1,
        embedding_model=embedder.model_name,
        source="edgar",
    )
    db_session.add(filing)
    db_session.flush()
    text = "Liquidity risk increased because refinancing costs rose."
    db_session.add(
        FilingChunk(
            filing_id=filing.id,
            chunk_index=0,
            content=text,
            section="Item 1A Risk Factors",
            embedding=embedder.embed_query(text),
        )
    )
    db_session.commit()


def test_missing_llm_credentials_raise_stable_application_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        get_llm()


def test_openai_provider_exception_is_wrapped_as_llm_error():
    llm = OpenAILLM.__new__(OpenAILLM)
    llm.model = "test-model"
    llm._client = _ExplodingOpenAIClient()

    with pytest.raises(LLMError, match="LLM provider request failed"):
        llm.complete("question", "system")


def test_query_endpoint_maps_llm_provider_failure_to_503(client, db_session, monkeypatch):
    _seed_queryable_filing(db_session)
    monkeypatch.setattr("sec_filings.rag.query.get_llm", lambda: FailingLLM())

    response = client.post(
        "/api/v1/query",
        json={"prompt": "What changed about liquidity risk?", "ticker": "LLMFAIL"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "simulated upstream LLM outage"
