import json

import pytest
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type

from sec_filings.mcp.server import call_mcp_tool, list_mcp_tools
from sec_filings.mcp.tools import ADK_TOOLS, tools_by_name


def test_adk_tools_convert_to_mcp_schema():
    names = {tool.name for tool in ADK_TOOLS}
    assert "ingest_sec_filings" in names
    assert "query_sec_filings" in names
    schemas = [adk_to_mcp_tool_type(tool) for tool in ADK_TOOLS]
    assert {schema.name for schema in schemas} == names
    ingest = next(schema for schema in schemas if schema.name == "ingest_sec_filings")
    assert ingest.description
    assert ingest.inputSchema


@pytest.mark.asyncio
async def test_mcp_list_and_call_tools(app, fake_edgar):
    listed = await list_mcp_tools()
    assert any(tool.name == "resolve_company" for tool in listed)

    result = await call_mcp_tool("resolve_company", {"ticker": "AAPL"})
    payload = json.loads(result[0].text)
    assert payload["ticker"] == "AAPL"
    assert payload["cik"] == "0000320193"

    ingest = await call_mcp_tool(
        "ingest_sec_filings",
        {"ticker": "AAPL", "form_types": "10-K", "limit": 1},
    )
    ingest_payload = json.loads(ingest[0].text)
    stored = ingest_payload.get("ingested") or ingest_payload.get("skipped")
    assert stored

    query = await call_mcp_tool(
        "query_sec_filings",
        {"prompt": "What risk factors are disclosed?", "ticker": "AAPL"},
    )
    query_payload = json.loads(query[0].text)
    assert query_payload["answer"]
    assert query_payload["citations"]

    missing = await call_mcp_tool("not_a_real_tool", {})
    assert "error" in json.loads(missing[0].text)


def test_function_tool_catalog_matches_wrappers():
    catalog = tools_by_name()
    assert catalog["list_watchlist"].func.__name__ == "list_watchlist"
