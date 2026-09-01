"""ADK agent that uses the same FunctionTools the MCP server exposes.

Run from the repo root:

    adk web agents

or:

    adk run agents/sec_filings_agent
"""

from google.adk.agents import LlmAgent

from sec_filings.mcp.tools import ADK_TOOLS

root_agent = LlmAgent(
    model="gemini-flash-latest",
    name="sec_filings_agent",
    description="Research assistant for SEC 10-K, 10-Q, and 8-K filings stored in Postgres/pgvector.",
    instruction=(
        "You help analysts work with SEC filings. Prefer tools over guessing. "
        "Resolve a ticker before ingesting. After ingest, query_sec_filings for questions "
        "and cite ticker, form type, filing date, and section from the tool output. "
        "If nothing is indexed yet, ingest recent 10-K filings first."
    ),
    tools=list(ADK_TOOLS),
)
