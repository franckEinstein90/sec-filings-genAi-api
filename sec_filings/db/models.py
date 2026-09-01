from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sec_filings.config import EMBEDDING_DIMENSIONS
from sec_filings.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cik: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    ticker: Mapped[Optional[str]] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(512))
    sic: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    sic_description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    exchanges: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    filings: Mapped[list["Filing"]] = relationship(back_populates="company")
    holdings: Mapped[list["Holding"]] = relationship(back_populates="company")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "cik": self.cik,
            "ticker": self.ticker,
            "name": self.name,
            "sic": self.sic,
            "sic_description": self.sic_description,
            "exchanges": self.exchanges,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Filing(Base):
    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    accession_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    form_type: Mapped[str] = mapped_column(String(16), index=True)
    filing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    report_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    primary_document: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="edgar")
    edgar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    company: Mapped["Company"] = relationship(back_populates="filings")
    chunks: Mapped[list["FilingChunk"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )

    def to_dict(self, include_company: bool = False) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "company_id": self.company_id,
            "accession_number": self.accession_number,
            "form_type": self.form_type,
            "filing_date": self.filing_date.isoformat() if self.filing_date else None,
            "report_date": self.report_date.isoformat() if self.report_date else None,
            "primary_document": self.primary_document,
            "source": self.source,
            "edgar_url": self.edgar_url,
            "title": self.title,
            "description": self.description,
            "processing_status": self.processing_status,
            "processing_error": self.processing_error,
            "chunk_count": self.chunk_count,
            "embedding_model": self.embedding_model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_company and self.company is not None:
            payload["company"] = self.company.to_dict()
        return payload


class FilingChunk(Base):
    __tablename__ = "filing_chunks"
    __table_args__ = (
        UniqueConstraint("filing_id", "chunk_index", name="uq_filing_chunks_filing_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filing_id: Mapped[int] = mapped_column(
        ForeignKey("filings.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    section: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))

    filing: Mapped["Filing"] = relationship(back_populates="chunks")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "filing_id": self.filing_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "section": self.section,
            "token_count": self.token_count,
        }


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    holdings: Mapped[list["Holding"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )

    def to_dict(self, include_holdings: bool = False) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "holding_count": len(self.holdings) if self.holdings is not None else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_holdings:
            payload["holdings"] = [holding.to_dict() for holding in self.holdings]
        return payload


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "company_id", name="uq_holdings_portfolio_company"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    ticker: Mapped[str] = mapped_column(String(16))
    shares: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    as_of: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="holdings")
    company: Mapped["Company"] = relationship(back_populates="holdings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "portfolio_id": self.portfolio_id,
            "company_id": self.company_id,
            "ticker": self.ticker,
            "name": self.company.name if self.company is not None else None,
            "cik": self.company.cik if self.company is not None else None,
            "shares": self.shares,
            "as_of": self.as_of.isoformat() if self.as_of else None,
        }
