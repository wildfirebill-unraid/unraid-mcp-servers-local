import os
import json
import subprocess
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("service-mcp")

BASE_PATH = Path(os.environ.get("SERVICE_MCP_PATH", "/data"))

def _run_systemctl(*args: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl"] + list(args),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr.strip() or result.stdout.strip()}"
        return result.stdout.strip() or "Success"
    except FileNotFoundError:
        return "Error: systemctl not found (not a systemd system)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out"

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_services",
            description="List systemd services and their status",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {"type": "string", "description": "Optional name filter"}
                },
            },
        ),
        Tool(
            name="service_status",
            description="Get detailed status of a service",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Service name"}
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="start_service",
            description="Start a systemd service",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Service name"}
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="stop_service",
            description="Stop a systemd service",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Service name"}
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="restart_service",
            description="Restart a systemd service",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Service name"}
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="enable_service",
            description="Enable a service to start on boot",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Service name"}
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="disable_service",
            description="Disable a service from starting on boot",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Service name"}
                },
                "required": ["name"],
            },
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "list_services":
        filt = arguments.get("filter", "")
        if filt:
            result = _run_systemctl("list-units", "--type=service", f"--name={filt}")
        else:
            result = _run_systemctl("list-units", "--type=service")
        return [TextContent(type="text", text=result)]

    svc = arguments.get("name", "")
    if name == "service_status":
        result = _run_systemctl("status", svc)
    elif name == "start_service":
        result = _run_systemctl("start", svc)
    elif name == "stop_service":
        result = _run_systemctl("stop", svc)
    elif name == "restart_service":
        result = _run_systemctl("restart", svc)
    elif name == "enable_service":
        result = _run_systemctl("enable", svc)
    elif name == "disable_service":
        result = _run_systemctl("disable", svc)
    else:
        result = f"Unknown tool: {name}"

    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="service-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
