import os
import json
from pathlib import Path
import fnmatch
import hashlib
from datetime import datetime, timezone
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("finder-mcp")

BASE_PATH = Path(os.environ.get("FINDER_PATH", "/data")).resolve()

def safe_path(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = BASE_PATH / p
    return p.resolve()

def walk(path: Path, max_depth: int | None = None, follow_links: bool = False):
    path = safe_path(str(path))
    depth = 0
    stack = [(path, depth)]
    while stack:
        current, depth = stack.pop(0)
        if max_depth is not None and depth > max_depth:
            continue
        try:
            if current.is_dir():
                for child in sorted(current.iterdir()):
                    stack.append((child, depth + 1))
                    yield child
            else:
                yield current
        except PermissionError:
            pass

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="find_by_name",
            description="Find files by name pattern (glob)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search"},
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. *.txt)"},
                    "max_depth": {"type": "integer", "description": "Max recursion depth"},
                    "follow_links": {"type": "boolean", "description": "Follow symlinks"}
                },
                "required": ["path", "pattern"]
            }
        ),
        Tool(
            name="find_by_size",
            description="Find files by size range",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search"},
                    "min_bytes": {"type": "integer", "description": "Minimum file size in bytes"},
                    "max_bytes": {"type": "integer", "description": "Maximum file size in bytes"},
                    "count": {"type": "integer", "description": "Max results to return"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="find_by_age",
            description="Find files by modification age",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search"},
                    "max_days_old": {"type": "number", "description": "Max age in days"},
                    "min_days_old": {"type": "number", "description": "Min age in days"},
                    "pattern": {"type": "string", "description": "Glob filter pattern"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="find_by_content",
            description="Find files containing specific text",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search"},
                    "query": {"type": "string", "description": "Text to search for"},
                    "pattern": {"type": "string", "description": "Glob filter (e.g. *.txt)"},
                    "max_size_mb": {"type": "integer", "description": "Skip files larger than this in MB"}
                },
                "required": ["path", "query"]
            }
        ),
        Tool(
            name="find_empty",
            description="Find empty files and directories",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="find_by_type",
            description="Find files by type (file/directory/symlink)",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search"},
                    "type": {"type": "string", "description": "Type: file, directory, symlink"},
                    "pattern": {"type": "string", "description": "Glob filter pattern"},
                    "max_depth": {"type": "integer", "description": "Max recursion depth"}
                },
                "required": ["path", "type"]
            }
        ),
        Tool(
            name="duplicate_finder",
            description="Find duplicate files by name+size or sha256 hash",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search"},
                    "method": {"type": "string", "description": "Comparison method: name_size or sha256"},
                    "min_size": {"type": "integer", "description": "Minimum file size in bytes to consider"}
                },
                "required": ["path", "method"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    search_path = safe_path(str(arguments.get("path", "")))
    if name == "find_by_name":
        pattern = arguments["pattern"]
        max_depth = arguments.get("max_depth")
        follow_links = arguments.get("follow_links", False)
        results = []
        for entry in walk(search_path, max_depth, follow_links):
            if fnmatch.fnmatch(entry.name, pattern):
                try:
                    stat = entry.stat()
                except OSError:
                    continue
                results.append({
                    "path": str(entry),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                })
        result = json.dumps({"matches": results, "count": len(results)})
    elif name == "find_by_size":
        min_bytes = arguments.get("min_bytes")
        max_bytes = arguments.get("max_bytes")
        count = arguments.get("count")
        results = []
        for entry in walk(search_path):
            try:
                if entry.is_file():
                    size = entry.stat().st_size
                    if (min_bytes is None or size >= min_bytes) and (max_bytes is None or size <= max_bytes):
                        results.append({"path": str(entry), "size": size})
                        if count and len(results) >= count:
                            break
            except OSError:
                continue
        result = json.dumps({"matches": results, "count": len(results)})
    elif name == "find_by_age":
        min_days = arguments.get("min_days_old")
        max_days = arguments.get("max_days_old")
        pattern = arguments.get("pattern")
        now = datetime.now(tz=timezone.utc).timestamp()
        day_secs = 86400
        results = []
        for entry in walk(search_path):
            if pattern and not fnmatch.fnmatch(entry.name, pattern):
                continue
            try:
                mtime = entry.stat().st_mtime
                age_days = (now - mtime) / day_secs
                if (max_days is None or age_days <= max_days) and (min_days is None or age_days >= min_days):
                    results.append({
                        "path": str(entry),
                        "age_days": round(age_days, 2),
                        "modified": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                    })
            except OSError:
                continue
        result = json.dumps({"matches": results, "count": len(results)})
    elif name == "find_by_content":
        query = arguments["query"]
        pattern = arguments.get("pattern")
        max_size_mb = arguments.get("max_size_mb")
        max_bytes = max_size_mb * 1024 * 1024 if max_size_mb else None
        results = []
        for entry in walk(search_path):
            if pattern and not fnmatch.fnmatch(entry.name, pattern):
                continue
            try:
                if not entry.is_file():
                    continue
                size = entry.stat().st_size
                if max_bytes and size > max_bytes:
                    continue
                text = entry.read_text(errors="replace")
                if query in text:
                    results.append({"path": str(entry), "size": size})
            except (OSError, UnicodeDecodeError):
                continue
        result = json.dumps({"matches": results, "count": len(results)})
    elif name == "find_empty":
        empty_files = []
        empty_dirs = []
        for entry in walk(search_path):
            try:
                if entry.is_file() and entry.stat().st_size == 0:
                    empty_files.append(str(entry))
                elif entry.is_dir() and not any(entry.iterdir()):
                    empty_dirs.append(str(entry))
            except OSError:
                continue
        result = json.dumps({"empty_files": empty_files, "empty_directories": empty_dirs,
                             "file_count": len(empty_files), "dir_count": len(empty_dirs)})
    elif name == "find_by_type":
        ftype = arguments["type"]
        pattern = arguments.get("pattern")
        max_depth = arguments.get("max_depth")
        results = []
        for entry in walk(search_path, max_depth):
            if pattern and not fnmatch.fnmatch(entry.name, pattern):
                continue
            try:
                is_match = False
                if ftype == "file" and entry.is_file():
                    is_match = True
                elif ftype == "directory" and entry.is_dir():
                    is_match = True
                elif ftype == "symlink" and entry.is_symlink():
                    is_match = True
                if is_match:
                    stat = entry.stat()
                    results.append({
                        "path": str(entry),
                        "size": stat.st_size if not entry.is_dir() else 0,
                        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                    })
            except OSError:
                continue
        result = json.dumps({"matches": results, "count": len(results)})
    elif name == "duplicate_finder":
        method = arguments["method"]
        min_size = arguments.get("min_size", 0)
        by_key: dict = {}
        for entry in walk(search_path):
            try:
                if not entry.is_file():
                    continue
                stat = entry.stat()
                if stat.st_size < min_size:
                    continue
                if method == "name_size":
                    key = (entry.name, stat.st_size)
                else:
                    key = hashlib.sha256(entry.read_bytes()).hexdigest()
                by_key.setdefault(key, []).append(str(entry))
            except OSError:
                continue
        duplicates = {k: v for k, v in by_key.items() if len(v) > 1}
        groups = []
        for key, paths in duplicates.items():
            label = str(key[0] if isinstance(key, tuple) else key[:12])
            groups.append({"key": label, "paths": paths, "count": len(paths)})
        result = json.dumps({"groups": groups, "total_duplicate_groups": len(groups)})
    else:
        raise ValueError(f"Unknown tool: {name}")
    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="finder-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
