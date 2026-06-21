import os
import json
import subprocess
import tempfile
from pathlib import Path
import difflib
import fnmatch
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

BASE = Path(os.environ.get("DIFF_BASE_PATH", "/data"))
server = Server("diff-mcp")

def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else BASE / path

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="diff_text", description="Compare two text strings", inputSchema={"type": "object", "properties": {"text1": {"type": "string"}, "text2": {"type": "string"}, "context_lines": {"type": "integer", "default": 3}, "unified": {"type": "boolean", "default": True}}, "required": ["text1", "text2"]}),
        Tool(name="diff_files", description="Compare two files", inputSchema={"type": "object", "properties": {"file1": {"type": "string"}, "file2": {"type": "string"}, "context_lines": {"type": "integer", "default": 3}}, "required": ["file1", "file2"]}),
        Tool(name="diff_directories", description="Compare two directories", inputSchema={"type": "object", "properties": {"dir1": {"type": "string"}, "dir2": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["dir1", "dir2"]}),
        Tool(name="patch_text", description="Apply a unified diff patch to text", inputSchema={"type": "object", "properties": {"original": {"type": "string"}, "patch": {"type": "string"}}, "required": ["original", "patch"]}),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "diff_text":
        text1 = arguments["text1"].splitlines(keepends=True)
        text2 = arguments["text2"].splitlines(keepends=True)
        n = arguments.get("context_lines", 3)
        unified = arguments.get("unified", True)
        if unified:
            result = "".join(difflib.unified_diff(text1, text2, n=n))
        else:
            result = "".join(difflib.context_diff(text1, text2, n=n))
        return [TextContent(type="text", text=result)]
    elif name == "diff_files":
        file1 = _resolve(arguments["file1"])
        file2 = _resolve(arguments["file2"])
        with open(file1) as f:
            t1 = f.readlines()
        with open(file2) as f:
            t2 = f.readlines()
        n = arguments.get("context_lines", 3)
        result = "".join(difflib.unified_diff(t1, t2, fromfile=str(file1), tofile=str(file2), n=n))
        return [TextContent(type="text", text=result)]
    elif name == "diff_directories":
        dir1 = _resolve(arguments["dir1"])
        dir2 = _resolve(arguments["dir2"])
        pattern = arguments.get("pattern", "*")
        files1 = {p.relative_to(dir1) for p in dir1.rglob(pattern) if p.is_file()}
        files2 = {p.relative_to(dir2) for p in dir2.rglob(pattern) if p.is_file()}
        all_files = files1 | files2
        results = {}
        for rel in sorted(all_files):
            p1 = dir1 / rel
            p2 = dir2 / rel
            if not p1.exists():
                results[str(rel)] = "only in dir2"
            elif not p2.exists():
                results[str(rel)] = "only in dir1"
            else:
                with open(p1) as f:
                    t1 = f.readlines()
                with open(p2) as f:
                    t2 = f.readlines()
                diff = "".join(difflib.unified_diff(t1, t2, fromfile=str(p1), tofile=str(p2)))
                if diff:
                    results[str(rel)] = diff
        return [TextContent(type="text", text=json.dumps(results, indent=2))]
    elif name == "patch_text":
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as orig:
            orig.write(arguments["original"])
            orig_path = orig.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as pf:
            pf.write(arguments["patch"])
            patch_path = pf.name
        try:
            result = subprocess.run(["patch", "--forward", orig_path, patch_path], capture_output=True, text=True)
            if result.returncode != 0 and result.returncode != 1:
                raise RuntimeError(result.stderr.strip())
            with open(orig_path) as f:
                patched = f.read()
            return [TextContent(type="text", text=patched)]
        finally:
            Path(orig_path).unlink(missing_ok=True)
            Path(patch_path).unlink(missing_ok=True)
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationOptions(server_name="diff-mcp", server_version="1.0.0"),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
