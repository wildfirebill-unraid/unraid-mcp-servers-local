import os
import json
import subprocess
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

BASE = os.environ.get("MEDIA_INFO_PATH", "/data")

def resolve_path(user_path: str) -> str:
    p = os.path.normpath(os.path.join(BASE, user_path))
    if not p.startswith(os.path.normpath(BASE)):
        raise ValueError("Path traversal denied")
    if not os.path.exists(p):
        raise FileNotFoundError(f"Path not found: {p}")
    return p

def run_ffprobe(path: str, args: list[str] | None = None) -> dict:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json"]
    if args:
        cmd.extend(args)
    cmd.append(path)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error: {result.stderr}")
    return json.loads(result.stdout)

server = Server("media-info-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="media_info",
            description="Get media file metadata using ffprobe",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to media file relative to MEDIA_INFO_PATH"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="media_streams",
            description="List all streams in a media file with detailed codec info",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to media file"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="media_format",
            description="Get container format info (format name, size, bitrate, duration)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to media file"}
                },
                "required": ["path"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    resolved = resolve_path(arguments["path"])
    if name == "media_info":
        data = run_ffprobe(resolved)
        return [TextContent(type="text", text=json.dumps(data, indent=2))]
    elif name == "media_streams":
        data = run_ffprobe(resolved, ["-show_streams"])
        return [TextContent(type="text", text=json.dumps(data.get("streams", []), indent=2))]
    elif name == "media_format":
        data = run_ffprobe(resolved, ["-show_format"])
        return [TextContent(type="text", text=json.dumps(data.get("format", {}), indent=2))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="media-info-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
