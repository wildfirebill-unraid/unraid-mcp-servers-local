import os
import fnmatch
import hashlib
import time
from pathlib import Path
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("filesystem-mcp")

ALLOWED_BASE = os.environ.get("FILESYSTEM_ALLOWED_PATH", "/data")

def _resolve_path(requested: str) -> Path:
    base = Path(ALLOWED_BASE).resolve()
    target = (base / requested).resolve()
    if not str(target).startswith(str(base)):
        raise PermissionError(f"Path {requested} is outside allowed base {ALLOWED_BASE}")
    return target

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_directory",
            description="List files and directories at the given path",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path within allowed directory"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="read_file",
            description="Read contents of a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="write_file",
            description="Write content to a file (creates parent directories)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="search_files",
            description="Search for files matching a glob pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern like '**/*.txt'"},
                    "path": {"type": "string", "description": "Subdirectory to search within"}
                },
                "required": ["pattern"]
            }
        ),
        Tool(
            name="file_info",
            description="Get metadata about a file or directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="delete_file",
            description="Delete a file or empty directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to file or directory"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="grep_files",
            description="Search file contents for a regex pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "glob": {"type": "string", "description": "File glob to restrict search (e.g. '*.py')"},
                    "path": {"type": "string", "description": "Subdirectory to search"}
                },
                "required": ["pattern"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = ""
    if name == "list_directory":
        target = _resolve_path(arguments["path"])
        entries = []
        for entry in os.listdir(target):
            fp = target / entry
            typ = "directory" if fp.is_dir() else "file"
            size = fp.stat().st_size if fp.is_file() else 0
            entries.append({"name": entry, "type": typ, "size": size})
        result = str(entries)
    elif name == "read_file":
        target = _resolve_path(arguments["path"])
        result = target.read_text(encoding="utf-8")
    elif name == "write_file":
        target = _resolve_path(arguments["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(arguments["content"], encoding="utf-8")
        result = f"Written {len(arguments['content'])} bytes to {arguments['path']}"
    elif name == "search_files":
        base = Path(ALLOWED_BASE).resolve()
        search_path = base
        if "path" in arguments:
            search_path = _resolve_path(arguments["path"])
        matches = []
        for root, dirs, files in os.walk(search_path):
            rel_root = os.path.relpath(root, base)
            for f in files:
                if fnmatch.fnmatch(f, arguments["pattern"]):
                    matches.append(os.path.join(rel_root, f))
            for d in dirs:
                if fnmatch.fnmatch(d, arguments["pattern"]):
                    matches.append(os.path.join(rel_root, d))
        result = str(matches)
    elif name == "file_info":
        target = _resolve_path(arguments["path"])
        stat = target.stat()
        result = str({
            "size": stat.st_size,
            "modified": time.ctime(stat.st_mtime),
            "created": time.ctime(stat.st_ctime),
            "is_dir": target.is_dir(),
            "is_file": target.is_file(),
            "permissions": oct(stat.st_mode)[-3:]
        })
    elif name == "delete_file":
        target = _resolve_path(arguments["path"])
        if target.is_dir():
            target.rmdir()
        else:
            target.unlink()
        result = f"Deleted {arguments['path']}"
    elif name == "grep_files":
        import re
        base = Path(ALLOWED_BASE).resolve()
        search_path = base
        if "path" in arguments:
            search_path = _resolve_path(arguments["path"])
        pat = re.compile(arguments["pattern"])
        file_pat = arguments.get("glob", "*")
        matches = []
        for root, dirs, files in os.walk(search_path):
            for f in files:
                if not fnmatch.fnmatch(f, file_pat):
                    continue
                fp = Path(root) / f
                try:
                    for i, line in enumerate(fp.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                        if pat.search(line):
                            rel = os.path.relpath(fp, base)
                            matches.append(f"{rel}:{i}: {line.strip()[:200]}")
                except Exception:
                    pass
        result = str(matches)
    else:
        raise ValueError(f"Unknown tool: {name}")
    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="filesystem-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
