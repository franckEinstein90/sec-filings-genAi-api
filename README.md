# SEC Filings GenAI API

FastAPI service that pulls SEC filings from EDGAR, chunks them, stores embeddings in **Postgres + pgvector**, and answers questions with retrieval-augmented generation.

The same tools are also exposed as an **MCP server built with Google ADK** (`FunctionTool` + `adk_to_mcp_tool_type`), so Cursor, Claude, or any MCP client can ingest and query filings.

There is no separate database install required for local development: `pgserver` ships a Postgres 16 binary (with the `vector` extension) and this app starts it from Python. Point `DATABASE_URL` at any Postgres that has pgvector when you want a durable server instead.

The companion UI is [sec-filings-genAi-app](https://github.com/franckEinstein90/sec-filings-genAi-app).

## What it does

- Resolve issuers by ticker via EDGAR (`company_tickers.json` + submissions)
- Ingest 10-K / 10-Q / 8-K documents (or upload HTML/PDF/text)
- Split on Item headings where possible, then recursively chunk
- Embed with OpenAI (`text-embedding-3-small` by default) and store in `filing_chunks.embedding`
- Query with cosine similarity over pgvector and cite ticker, form, date, and section
- Track a watchlist/portfolio of holdings
- Serve the same operations over MCP for agents

## Quick start (embedded Postgres)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set OPENAI_API_KEY, GOOGLE_API_KEY (for the ADK agent), and a SEC_USER_AGENT that includes your email

python -m sec_filings.db.bootstrap   # starts embedded Postgres, enables pgvector, runs Alembic
python main.py                       # http://localhost:5000/health  and  /docs
```

OpenAPI lives at `/docs`. Data directory defaults to `.pgdata/` (gitignored). Override with `PGDATA_DIR`.

## MCP server (Google ADK)

The stdio MCP server wraps ADK `FunctionTool`s and converts them with `adk_to_mcp_tool_type`:

```bash
python -m sec_filings.mcp.server
```

Cursor / Claude Desktop config:

```json
{
  "mcpServers": {
    "sec-filings": {
      "command": "python",
      "args": ["-m", "sec_filings.mcp.server"],
      "cwd": "/absolute/path/to/sec-filings-genAi-api"
    }
  }
}
```

Tools: `resolve_company`, `ingest_sec_filings`, `list_indexed_filings`, `query_sec_filings`, `add_watchlist_holding`, `list_watchlist`.

### ADK agent UI

```bash
adk web agents
```

Then pick `sec_filings_agent`. The agent uses the same FunctionTools the MCP server exposes. Set `GOOGLE_API_KEY` for Gemini.

## Optional: Docker Postgres

```bash
docker compose up -d
export DATABASE_URL=postgresql+psycopg://sec:sec@localhost:5432/sec_filings
python -m sec_filings.db.bootstrap
```

## Schema and migrations

SQLAlchemy models live in `sec_filings/db/models.py`. Alembic versions live in `alembic/versions/`.

```bash
python -m sec_filings.db.bootstrap
alembic revision -m "add_something" --autogenerate
alembic upgrade head
```

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process is up |
| GET | `/api/v1/ready` | Postgres + pgvector are up |
| GET/POST | `/api/v1/companies` | List or resolve a ticker from EDGAR |
| GET | `/api/v1/companies/<cik-or-ticker>` | Company plus ingested filings |
| POST | `/api/v1/filings/ingest` | `{ "ticker": "AAPL", "form_types": ["10-K"], "limit": 1 }` |
| POST | `/api/v1/filings/upload` | multipart `file` + `ticker` (+ optional `form_type`) |
| GET | `/api/v1/filings` | Filter with `ticker`, `cik`, `form_type` |
| DELETE | `/api/v1/filings/<id>` | Drop a filing and its chunks |
| POST | `/api/v1/query` | `{ "prompt": "...", "ticker": "AAPL" }` |
| GET | `/api/v1/portfolio` | Default watchlist |
| POST | `/api/v1/portfolios` | Create a named portfolio |
| POST | `/api/v1/portfolios/<id>/holdings` | `{ "ticker": "AAPL", "shares": 10 }` |

EDGAR requires a descriptive `User-Agent` with contact info. Set `SEC_USER_AGENT`.

## Tests

```bash
EMBEDDING_PROVIDER=hash LLM_PROVIDER=mock pytest -q
```

## Layout

```
sec_filings/
  app.py        FastAPI factory
  routes/       HTTP routers
  db/           models, embedded Postgres, Alembic bootstrap
  edgar/        EDGAR client and HTML/PDF text extraction
  embeddings/   OpenAI + deterministic hash embedder (tests)
  rag/          chunking, similarity query, LLM answer
  services/     ingest pipeline
  mcp/          Google ADK FunctionTools + MCP stdio server
agents/sec_filings_agent/   ADK-discoverable agent
alembic/versions/
```
