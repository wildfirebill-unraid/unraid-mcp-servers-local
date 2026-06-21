import os
import json
import re
import glob
import time
import asyncio
from collections import Counter
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

BASE = os.environ.get("LOG_PATH", "/data")

def resolve_path(user_path: str) -> str:
    p = os.path.normpath(os.path.join(BASE, user_path))
    if not p.startswith(os.path.normpath(BASE)):
        raise ValueError("Path traversal denied")
    return p

def read_last_lines(path: str, n: int) -> list[str]:
    with open(path, "r", errors="replace") as f:
        lines = f.readlines()
    return lines[-n:]

server = Server("log-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="tail_log",
            description="Tail last N lines of a log file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to log file"},
                    "lines": {"type": "integer", "description": "Number of lines to retrieve", "default": 50},
                    "follow": {"type": "boolean", "description": "Keep reading new lines", "default": False}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="search_log",
            description="Search log file for regex pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to log file"},
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "context_lines": {"type": "integer", "description": "Lines of context before/after match", "default": 0},
                    "ignore_case": {"type": "boolean", "description": "Case insensitive search", "default": False}
                },
                "required": ["path", "pattern"]
            }
        ),
        Tool(
            name="log_summary",
            description="Count log levels (ERROR/WARN/INFO) in a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to log file"},
                    "pattern": {"type": "string", "description": "Custom regex for level detection"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="list_log_files",
            description="Find log files in directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                    "pattern": {"type": "string", "description": "Glob pattern like *.log or *.txt", "default": "*.log"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="watch_log",
            description="Watch a log file for new lines matching a pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to log file"},
                    "pattern": {"type": "string", "description": "Pattern to match new lines"},
                    "timeout_seconds": {"type": "integer", "description": "Max time to watch in seconds", "default": 30}
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
    if name == "tail_log":
        path = resolve_path(arguments["path"])
        n = arguments.get("lines", 50)
        lines = read_last_lines(path, n)
        result = "".join(lines)
        if arguments.get("follow", False):
            initial_count = len(lines)
            elapsed = 0
            while elapsed < 30:
                current_lines = read_last_lines(path, n)
                new_count = len(current_lines)
                if new_count > initial_count:
                    new_data = current_lines[-(new_count - initial_count):]
                    result += "".join(new_data)
                    initial_count = new_count
                await asyncio.sleep(1)
                elapsed += 1
        return [TextContent(type="text", text=result)]
    elif name == "search_log":
        path = resolve_path(arguments["path"])
        raw_pattern = arguments["pattern"]
        ctx = arguments.get("context_lines", 0)
        ic = arguments.get("ignore_case", False)
        flags = re.IGNORECASE if ic else 0
        compiled = re.compile(raw_pattern, flags)
        results = []
        with open(path, "r", errors="replace") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if compiled.search(line):
                start = max(0, i - ctx)
                end = min(len(lines), i + ctx + 1)
                entry = {"line": i + 1, "text": line.rstrip()}
                if ctx > 0:
                    entry["context"] = [l.rstrip() for l in lines[start:end]]
                    entry["context_start"] = start + 1
                results.append(entry)
        return [TextContent(type="text", text=json.dumps(results, indent=2))]
    elif name == "log_summary":
        path = resolve_path(arguments["path"])
        pattern = arguments.get("pattern")
        if pattern:
            compiled = re.compile(pattern)
        else:
            compiled = re.compile(r"\b(ERROR|WARN(ING)?|INFO|DEBUG|TRACE|FATAL|CRITICAL)\b", re.IGNORECASE)
        counts: Counter = Counter()
        with open(path, "r", errors="replace") as f:
            for line in f:
                for match in compiled.finditer(line):
                    level = match.group(0).upper()
                    if level in ("WARNING",):
                        level = "WARN"
                    counts[level] += 1
        total_lines = 0
        with open(path, "r", errors="replace") as f:
            total_lines = sum(1 for _ in f)
        return [TextContent(type="text", text=json.dumps({
            "file": path,
            "total_lines": total_lines,
            "level_counts": dict(counts.most_common())
        }, indent=2))]
    elif name == "list_log_files":
        dir_path = resolve_path(arguments["path"])
        pattern = arguments.get("pattern", "*.log")
        search_path = os.path.join(dir_path, pattern)
        files = []
        for f in glob.glob(search_path):
            st = os.stat(f)
            files.append({
                "name": os.path.basename(f),
                "path": f,
                "size": st.st_size,
                "modified": st.st_mtime
            })
        files.sort(key=lambda x: x["modified"], reverse=True)
        return [TextContent(type="text", text=json.dumps(files, indent=2, default=str))]
    elif name == "watch_log":
        path = resolve_path(arguments["path"])
        raw_pattern = arguments["pattern"]
        timeout = arguments.get("timeout_seconds", 30)
        compiled = re.compile(raw_pattern)
        start_size = os.path.getsize(path)
        matched = []
        elapsed = 0
        while elapsed < timeout:
            try:
                current_size = os.path.getsize(path)
                if current_size > start_size:
                    with open(path, "r", errors="replace") as f:
                        f.seek(start_size)
                        new_content = f.read()
                    for line in new_content.splitlines():
                        if compiled.search(line):
                            matched.append(line)
                    start_size = current_size
                    if matched:
                        break
            except (IOError, OSError):
                pass
            await asyncio.sleep(1)
            elapsed += 1
        return [TextContent(type="text", text=json.dumps({
            "matched_lines": matched,
            "total_matches": len(matched),
            "elapsed_seconds": elapsed
        }, indent=2))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="log-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
