import os
import json
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio
import subprocess

BASE = Path(os.environ.get("GIT_BASE_PATH", "/data"))
server = Server("git-mcp")

def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else BASE / path

def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="git_status", description="Show working tree status", inputSchema={"type": "object", "properties": {"repo_path": {"type": "string"}}, "required": ["repo_path"]}),
        Tool(name="git_log", description="Show commit log", inputSchema={"type": "object", "properties": {"repo_path": {"type": "string"}, "max_count": {"type": "integer", "default": 10}, "branch": {"type": "string"}}, "required": ["repo_path"]}),
        Tool(name="git_diff", description="Show diff of unstaged changes", inputSchema={"type": "object", "properties": {"repo_path": {"type": "string"}, "staged": {"type": "boolean", "default": False}}, "required": ["repo_path"]}),
        Tool(name="git_branches", description="List branches", inputSchema={"type": "object", "properties": {"repo_path": {"type": "string"}, "all": {"type": "boolean", "default": False}}, "required": ["repo_path"]}),
        Tool(name="git_commit_info", description="Get details of a specific commit", inputSchema={"type": "object", "properties": {"repo_path": {"type": "string"}, "commit_hash": {"type": "string"}}, "required": ["repo_path", "commit_hash"]}),
        Tool(name="git_blame", description="Show blame info for a file", inputSchema={"type": "object", "properties": {"repo_path": {"type": "string"}, "file_path": {"type": "string"}}, "required": ["repo_path", "file_path"]}),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    repo = _resolve(arguments["repo_path"])
    if name == "git_status":
        out = _git(["status"], repo)
        return [TextContent(type="text", text=out)]
    elif name == "git_log":
        args = ["log", f"--max-count={arguments.get('max_count', 10)}", "--format=medium"]
        if arguments.get("branch"):
            args.append(arguments["branch"])
        out = _git(args, repo)
        return [TextContent(type="text", text=out)]
    elif name == "git_diff":
        args = ["diff"]
        if arguments.get("staged"):
            args.append("--staged")
        out = _git(args, repo)
        return [TextContent(type="text", text=out)]
    elif name == "git_branches":
        args = ["branch"]
        if arguments.get("all"):
            args.append("--all")
        out = _git(args, repo)
        return [TextContent(type="text", text=out)]
    elif name == "git_commit_info":
        out = _git(["show", "--format=fuller", "--stat", arguments["commit_hash"]], repo)
        return [TextContent(type="text", text=out)]
    elif name == "git_blame":
        file = _resolve(arguments["file_path"])
        out = _git(["blame", str(file.relative_to(repo) if file.is_relative_to(repo) else file)], repo)
        return [TextContent(type="text", text=out)]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationOptions(server_name="git-mcp", server_version="1.0.0"),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
