from sqlalchemy import text
from fastapi import APIRouter

from sec_filings.db.bootstrap import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/api/v1/ready")
def ready():
    engine = get_engine()
    with engine.connect() as conn:
        vector = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        db = conn.execute(text("SELECT current_database()")).scalar()
    return {"status": "ready", "database": db, "pgvector": vector}
