from __future__ import annotations

from pydantic import BaseModel, Field


class CompanyCreate(BaseModel):
    ticker: str = Field(..., min_length=1)


class IngestRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    form_types: list[str] | None = None
    limit: int | None = Field(default=None, ge=1, le=50)


class QueryRequest(BaseModel):
    prompt: str | None = None
    question: str | None = None
    ticker: str | None = None
    cik: str | None = None
    filing_id: int | None = None
    form_type: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)


class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None


class HoldingCreate(BaseModel):
    ticker: str = Field(..., min_length=1)
    shares: float | None = None
    as_of: str | None = None


class ErrorBody(BaseModel):
    error: str
