import os
import json
import time
import tempfile
import shutil
from pathlib import Path
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class TempDirServer(Server):
    def __init__(self):
        super().__init__("temp-dir")
        self._temp_base_path = os.environ.get("TEMP_BASE_PATH", "")
        if not self._temp_base_path:
            self._temp_base_path = str(Path(tempfile.gettempdir()) / "mcp-temp-dir")
        os.makedirs(self._temp_base_path, exist_ok=True)

    def _resolve_path(self, path: str) -> Path:
        p = Path(path).resolve()
        base = Path(self._temp_base_path).resolve()
        if not str(p).startswith(str(base)):
            raise ValueError(f"Path outside sandbox: {path}")
        return p

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="create_temp_dir", description="Create a temp directory in sandbox",
                 inputSchema={"type": "object", "properties": {
                     "prefix": {"type": "string", "description": "Prefix for dir name (default 'tmp')"}},
                     "required": []}),
            Tool(name="create_temp_file", description="Create a temp file with optional content",
                 inputSchema={"type": "object", "properties": {
                     "prefix": {"type": "string", "description": "Prefix (default 'tmp')"},
                     "suffix": {"type": "string", "description": "Suffix (default '.txt')"},
                     "content": {"type": "string", "description": "File content"}},
                     "required": []}),
            Tool(name="list_temp", description="List all items in sandbox",
                 inputSchema={"type": "object", "properties": {}, "required": []}),
            Tool(name="clean_temp", description="Remove old temp items",
                 inputSchema={"type": "object", "properties": {
                     "max_age_hours": {"type": "number", "description": "Max age in hours (default 24)"}},
                     "required": []}),
            Tool(name="temp_info", description="Show sandbox info",
                 inputSchema={"type": "object", "properties": {}, "required": []}),
            Tool(name="scratch_pad", description="Create a named scratch area",
                 inputSchema={"type": "object", "properties": {
                     "name": {"type": "string", "description": "Scratch name"}},
                     "required": ["name"]}),
            Tool(name="write_scratch", description="Write content to a scratch area",
                 inputSchema={"type": "object", "properties": {
                     "name": {"type": "string", "description": "Scratch name"},
                     "content": {"type": "string", "description": "Content to write"}},
                     "required": ["name", "content"]}),
            Tool(name="read_scratch", description="Read content from a scratch area",
                 inputSchema={"type": "object", "properties": {
                     "name": {"type": "string", "description": "Scratch name"}},
                     "required": ["name"]}),
            Tool(name="temp_tree", description="Tree view of sandbox",
                 inputSchema={"type": "object", "properties": {}, "required": []}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "create_temp_dir":
                result = self._create_temp_dir(args)
            elif name == "create_temp_file":
                result = self._create_temp_file(args)
            elif name == "list_temp":
                result = self._list_temp()
            elif name == "clean_temp":
                result = self._clean_temp(args)
            elif name == "temp_info":
                result = self._temp_info()
            elif name == "scratch_pad":
                result = self._scratch_pad(args)
            elif name == "write_scratch":
                result = self._write_scratch(args)
            elif name == "read_scratch":
                result = self._read_scratch(args)
            elif name == "temp_tree":
                result = self._temp_tree()
            else:
                raise ValueError(f"Unknown tool: {name}")
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    def _create_temp_dir(self, args: dict) -> dict:
        prefix = args.get("prefix", "tmp")
        d = tempfile.mkdtemp(prefix=prefix, dir=self._temp_base_path)
        return {"path": d}

    def _create_temp_file(self, args: dict) -> dict:
        prefix = args.get("prefix", "tmp")
        suffix = args.get("suffix", ".txt")
        content = args.get("content", "")
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=self._temp_base_path)
        os.close(fd)
        if content:
            Path(path).write_text(content, encoding="utf-8")
        return {"path": path, "size": len(content)}

    def _list_temp(self) -> dict:
        items = []
        for f in Path(self._temp_base_path).iterdir():
            stat = f.stat()
            items.append({
                "name": f.name,
                "type": "directory" if f.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
        return {"base": self._temp_base_path, "count": len(items), "items": items}

    def _clean_temp(self, args: dict) -> dict:
        max_age = args.get("max_age_hours", 24)
        cutoff = time.time() - max_age * 3600
        removed = 0
        for f in Path(self._temp_base_path).iterdir():
            if f.stat().st_mtime < cutoff:
                if f.is_dir():
                    shutil.rmtree(f)
                else:
                    f.unlink()
                removed += 1
        return {"removed": removed, "max_age_hours": max_age}

    def _temp_info(self) -> dict:
        base = Path(self._temp_base_path)
        file_count = sum(1 for f in base.rglob("*") if f.is_file())
        dir_count = sum(1 for f in base.rglob("*") if f.is_dir())
        total_size = sum(f.stat().st_size for f in base.rglob("*") if f.is_file())
        return {
            "base_path": self._temp_base_path,
            "files": file_count,
            "directories": dir_count,
            "total_size": total_size,
        }

    def _scratch_dir(self) -> Path:
        return Path(self._temp_base_path) / "_scratch"

    def _scratch_pad(self, args: dict) -> dict:
        name = args["name"]
        scratch = self._scratch_dir() / name
        scratch.mkdir(parents=True, exist_ok=True)
        return {"scratch": str(scratch), "name": name}

    def _write_scratch(self, args: dict) -> dict:
        name = args["name"]
        content = args["content"]
        scratch = self._scratch_dir() / name
        scratch.mkdir(parents=True, exist_ok=True)
        filepath = scratch / "data.txt"
        filepath.write_text(content, encoding="utf-8")
        return {"scratch": name, "written": len(content), "path": str(filepath)}

    def _read_scratch(self, args: dict) -> dict:
        name = args["name"]
        filepath = self._scratch_dir() / name / "data.txt"
        if not filepath.exists():
            raise ValueError(f"Scratch pad '{name}' not found")
        return {"scratch": name, "content": filepath.read_text(encoding="utf-8")}

    def _temp_tree(self) -> dict:
        lines = ["."]
        base = Path(self._temp_base_path)
        for f in sorted(base.iterdir()):
            lines.append(f"  {'📁' if f.is_dir() else '📄'} {f.name}")
        return {"base": self._temp_base_path, "tree": "\n".join(lines)}

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = TempDirServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
