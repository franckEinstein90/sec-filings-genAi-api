from flask import Blueprint, jsonify, request

from sec_filings.rag.query import query_filings

query_bp = Blueprint("query", __name__, url_prefix="/api/v1")


@query_bp.post("/query")
def query():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or data.get("question") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    try:
        result = query_filings(
            prompt,
            ticker=data.get("ticker"),
            cik=data.get("cik"),
            filing_id=data.get("filing_id"),
            form_type=data.get("form_type"),
            top_k=data.get("top_k"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(result)
