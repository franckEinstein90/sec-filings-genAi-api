"""MCP stdio server that exposes ADK FunctionTools for SEC filings.

Official ADK pattern: wrap FunctionTool instances, advertise them with
``adk_to_mcp_tool_type``, and execute via ``FunctionTool.run_async``.

Logs go to stderr so they do not corrupt the stdio JSON-RPC stream.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from dotenv import load_dotenv
from mcp import types as mcp_types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type

from sec_filings.db.bootstrap import bootstrap_database
from sec_filings.mcp.tools import ADK_TOOLS, dump_tool_result, tools_by_name

load_dotenv()

logger = logging.getLogger("sec_filings.mcp")

mcp_app = Server("sec-filings-adk")


def _ensure_database() -> None:
    try:
        from sec_filings.db.bootstrap import get_engine

        get_engine()
    except RuntimeError:
        bootstrap_database()


@mcp_app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    _ensure_database()
    return [adk_to_mcp_tool_type(tool) for tool in ADK_TOOLS]


@mcp_app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.Content]:
    _ensure_database()
    catalog = tools_by_name()
    tool = catalog.get(name)
    if tool is None:
        payload = {"error": f"Tool '{name}' is not implemented by this server."}
        return [mcp_types.TextContent(type="text", text=json.dumps(payload))]
    try:
        result = await tool.run_async(args=arguments or {}, tool_context=None)
        return [mcp_types.TextContent(type="text", text=dump_tool_result(result))]
    except Exception as exc:  # noqa: BLE001 — surface tool failures to the MCP client
        logger.exception("ADK tool %s failed", name)
        payload = {"error": f"Failed to execute tool '{name}': {exc}"}
        return [mcp_types.TextContent(type="text", text=json.dumps(payload))]


async def run_stdio_server() -> None:
    _ensure_database()
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await mcp_app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=mcp_app.name,
                server_version="0.3.0",
                capabilities=mcp_app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run_stdio_server())
    except KeyboardInterrupt:
        logger.info("MCP server stopped")


if __name__ == "__main__":
    main()
