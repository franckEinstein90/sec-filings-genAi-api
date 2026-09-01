"""Flask application factory for the SEC filings RAG API."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, jsonify

from sec_filings.config import SECRET_KEY
from sec_filings.db.bootstrap import bootstrap_database
from sec_filings.db.session import SessionLocal
from sec_filings.routes import companies_bp, filings_bp, health_bp, portfolio_bp, query_bp


def create_app(
    *,
    testing: bool = False,
    database_url: str | None = None,
    pgdata: Path | None = None,
    bootstrap: bool = True,
) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["TESTING"] = testing
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
    app.config["JSON_SORT_KEYS"] = False

    if bootstrap:
        bootstrap_database(database_url=database_url, pgdata=pgdata)

    app.register_blueprint(health_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(filings_bp)
    app.register_blueprint(query_bp)
    app.register_blueprint(portfolio_bp)

    @app.teardown_appcontext
    def _remove_session(_exc: BaseException | None = None) -> None:
        SessionLocal.remove()

    @app.errorhandler(404)
    def _not_found(_e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def _method_not_allowed(_e):
        return jsonify({"error": "Method not allowed"}), 405

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    from sec_filings.config import FLASK_DEBUG, HOST, PORT

    application = create_app()
    application.run(host=HOST, port=PORT, debug=FLASK_DEBUG)


if __name__ == "__main__":
    main()
