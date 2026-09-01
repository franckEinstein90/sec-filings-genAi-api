"""Retrieve filing chunks from pgvector and generate an answer."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select

from sec_filings.config import RAG_TOP_K
from sec_filings.db.models import Company, Filing, FilingChunk
from sec_filings.db.session import get_session
from sec_filings.embeddings import get_embedder
from sec_filings.rag.llm import get_llm

SYSTEM_PROMPT = (
    "You are a financial research assistant. Answer the user's question using only "
    "the provided SEC filing excerpts. Cite ticker, form type, filing date, and "
    "section when you use a source. If the excerpts do not contain the answer, say so."
)


def query_filings(
    prompt: str,
    *,
    ticker: str | None = None,
    cik: str | None = None,
    filing_id: int | None = None,
    form_type: str | None = None,
    top_k: int | None = None,
) -> dict[str, Any]:
    if not prompt or not prompt.strip():
        raise ValueError("prompt is required")

    embedder = get_embedder()
    query_vector = embedder.embed_query(prompt.strip())
    k = top_k or RAG_TOP_K

    session = get_session()
    try:
        hits = _similarity_search(
            session,
            query_vector,
            ticker=ticker,
            cik=cik,
            filing_id=filing_id,
            form_type=form_type,
            top_k=k,
        )
        if not hits:
            return {
                "answer": "No indexed filings matched this query. Ingest a filing first.",
                "citations": [],
                "model": None,
                "usage": None,
            }

        context = _build_context(hits)
        llm = get_llm()
        completion = llm.complete(
            prompt=(
                f"Question:\n{prompt.strip()}\n\n"
                f"SEC filing excerpts:\n{context}\n\n"
                "Answer:"
            ),
            system_prompt=SYSTEM_PROMPT,
        )
        return {
            "answer": completion["content"],
            "citations": hits,
            "model": completion.get("model"),
            "usage": completion.get("usage"),
        }
    finally:
        session.close()


def _similarity_search(
    session,
    query_vector: list[float],
    *,
    ticker: str | None,
    cik: str | None,
    filing_id: int | None,
    form_type: str | None,
    top_k: int,
) -> list[dict[str, Any]]:
    distance = FilingChunk.embedding.cosine_distance(query_vector)
    stmt: Select = (
        select(
            FilingChunk,
            Filing,
            Company,
            distance.label("distance"),
        )
        .join(Filing, FilingChunk.filing_id == Filing.id)
        .join(Company, Filing.company_id == Company.id)
        .where(Filing.processing_status == "ready")
        .order_by(distance)
        .limit(top_k)
    )
    if filing_id is not None:
        stmt = stmt.where(Filing.id == filing_id)
    if ticker:
        stmt = stmt.where(Company.ticker == ticker.strip().upper())
    if cik:
        stmt = stmt.where(Company.cik == str(cik).zfill(10))
    if form_type:
        stmt = stmt.where(Filing.form_type == form_type.strip().upper())

    rows = session.execute(stmt).all()
    citations: list[dict[str, Any]] = []
    for chunk, filing, company, dist in rows:
        score = max(0.0, 1.0 - float(dist))
        citations.append(
            {
                "chunk_id": chunk.id,
                "filing_id": filing.id,
                "ticker": company.ticker,
                "cik": company.cik,
                "company": company.name,
                "form_type": filing.form_type,
                "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
                "section": chunk.section,
                "score": round(score, 4),
                "excerpt": chunk.content[:800],
                "edgar_url": filing.edgar_url,
            }
        )
    return citations


def _build_context(hits: list[dict[str, Any]]) -> str:
    blocks = []
    for i, hit in enumerate(hits, start=1):
        header = (
            f"[{i}] {hit.get('ticker')} {hit.get('form_type')} "
            f"{hit.get('filing_date') or ''} {hit.get('section') or ''}"
        ).strip()
        blocks.append(f"{header}\n{hit['excerpt']}")
    return "\n\n".join(blocks)
