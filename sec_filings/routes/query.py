from fastapi import APIRouter, HTTPException

from sec_filings.rag.query import query_filings
from sec_filings.schemas import QueryRequest

router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post("/query")
def query(body: QueryRequest):
    prompt = (body.prompt or body.question or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    try:
        return query_filings(
            prompt,
            ticker=body.ticker,
            cik=body.cik,
            filing_id=body.filing_id,
            form_type=body.form_type,
            top_k=body.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
