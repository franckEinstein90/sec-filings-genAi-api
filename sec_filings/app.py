"""FastAPI application factory for the SEC filings RAG API."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from sec_filings.db.bootstrap import bootstrap_database
from sec_filings.routes import (
    companies_router,
    filings_router,
    health_router,
    portfolio_router,
    query_router,
)


def create_app(
    *,
    testing: bool = False,
    database_url: str | None = None,
    pgdata: Path | None = None,
    bootstrap: bool = True,
) -> FastAPI:
    app = FastAPI(
        title="SEC Filings GenAI API",
        description="Ingest EDGAR filings into Postgres/pgvector and query them with RAG.",
        version="0.3.0",
        redirect_slashes=False,
    )
    app.state.testing = testing

    if bootstrap:
        bootstrap_database(database_url=database_url, pgdata=pgdata)

    app.include_router(health_router)
    app.include_router(companies_router)
    app.include_router(filings_router)
    app.include_router(query_router)
    app.include_router(portfolio_router)

    @app.exception_handler(HTTPException)
    async def _http_error(_request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": detail})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=400, content={"error": str(exc.errors())})

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    import uvicorn

    from sec_filings.config import FLASK_DEBUG, HOST, PORT

    uvicorn.run(
        "sec_filings.app:create_app",
        factory=True,
        host=HOST,
        port=PORT,
        reload=FLASK_DEBUG,
    )


if __name__ == "__main__":
    main()
