from flask import Blueprint, jsonify
from sqlalchemy import text

from sec_filings.db.bootstrap import get_engine

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@health_bp.get("/api/v1/ready")
def ready():
    engine = get_engine()
    with engine.connect() as conn:
        vector = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        db = conn.execute(text("SELECT current_database()")).scalar()
    return jsonify(
        {
            "status": "ready",
            "database": db,
            "pgvector": vector,
        }
    )
