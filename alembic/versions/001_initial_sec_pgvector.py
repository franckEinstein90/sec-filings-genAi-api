"""Initial SEC filings schema with pgvector.

Revision ID: 001_initial_sec_pgvector
Revises:
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from sec_filings.config import EMBEDDING_DIMENSIONS

revision = "001_initial_sec_pgvector"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("sic", sa.String(length=8), nullable=True),
        sa.Column("sic_description", sa.String(length=256), nullable=True),
        sa.Column("exchanges", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("cik"),
        sa.UniqueConstraint("ticker"),
    )
    op.create_index("ix_companies_cik", "companies", ["cik"])
    op.create_index("ix_companies_ticker", "companies", ["ticker"])

    op.create_table(
        "filings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("accession_number", sa.String(length=32), nullable=False),
        sa.Column("form_type", sa.String(length=16), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("primary_document", sa.String(length=256), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="edgar"),
        sa.Column("edgar_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("processing_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("accession_number"),
    )
    op.create_index("ix_filings_company_id", "filings", ["company_id"])
    op.create_index("ix_filings_accession_number", "filings", ["accession_number"])
    op.create_index("ix_filings_form_type", "filings", ["form_type"])
    op.create_index("ix_filings_processing_status", "filings", ["processing_status"])

    op.create_table(
        "filing_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filing_id", sa.Integer(), sa.ForeignKey("filings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("section", sa.String(length=128), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.UniqueConstraint("filing_id", "chunk_index", name="uq_filing_chunks_filing_index"),
    )
    op.create_index("ix_filing_chunks_filing_id", "filing_chunks", ["filing_id"])
    op.create_index("ix_filing_chunks_section", "filing_chunks", ["section"])
    op.execute(
        "CREATE INDEX ix_filing_chunks_embedding "
        "ON filing_chunks USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("shares", sa.Float(), nullable=True),
        sa.Column("as_of", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("portfolio_id", "company_id", name="uq_holdings_portfolio_company"),
    )
    op.create_index("ix_holdings_portfolio_id", "holdings", ["portfolio_id"])
    op.create_index("ix_holdings_company_id", "holdings", ["company_id"])


def downgrade() -> None:
    op.drop_table("holdings")
    op.drop_table("portfolios")
    op.drop_index("ix_filing_chunks_embedding", table_name="filing_chunks")
    op.drop_table("filing_chunks")
    op.drop_table("filings")
    op.drop_table("companies")
    op.execute("DROP EXTENSION IF EXISTS vector")
