import json
import os
import tomllib
import tomli_w
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


def _resolve_path(p: str) -> Path:
    raw = Path(p).resolve()
    allowed = os.environ.get("TOML_PATH", "")
    if allowed:
        allowed_root = Path(allowed).resolve()
        if not str(raw).startswith(str(allowed_root)):
            raise PermissionError(f"Access denied: {raw} is outside allowed path {allowed_root}")
    if not raw.exists():
        raise FileNotFoundError(f"File not found: {raw}")
    return raw


class TomlServer(Server):
    def __init__(self):
        super().__init__("toml-server")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="parse_toml",
                description="Parse a TOML file and return its contents as JSON",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to TOML file"}
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="toml_to_json",
                description="Convert a TOML file to JSON",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to TOML file"}
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="validate_toml",
                description="Validate TOML file syntax",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to TOML file"}
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="merge_toml",
                description="Merge multiple TOML files (last value wins)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of TOML file paths to merge",
                        }
                    },
                    "required": ["paths"],
                },
            ),
            Tool(
                name="format_toml",
                description="Format a TOML file (parse and rewrite in canonical form)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to TOML file"}
                    },
                    "required": ["path"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "parse_toml":
            return await self._parse_toml(args["path"])
        if name == "toml_to_json":
            return await self._toml_to_json(args["path"])
        if name == "validate_toml":
            return await self._validate_toml(args["path"])
        if name == "merge_toml":
            return await self._merge_toml(args["paths"])
        if name == "format_toml":
            return await self._format_toml(args["path"])
        raise ValueError(f"Unknown tool: {name}")

    def _read_toml(self, path: str) -> dict[str, Any]:
        resolved = _resolve_path(path)
        with open(resolved, "rb") as f:
            return tomllib.load(f)

    def _write_toml(self, path: str, data: dict[str, Any]) -> None:
        resolved = _resolve_path(path)
        with open(resolved, "wb") as f:
            tomli_w.dump(data, f)

    async def _parse_toml(self, path: str) -> list[TextContent]:
        data = self._read_toml(path)
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    async def _toml_to_json(self, path: str) -> list[TextContent]:
        data = self._read_toml(path)
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    async def _validate_toml(self, path: str) -> list[TextContent]:
        try:
            self._read_toml(path)
            return [TextContent(type="text", text=json.dumps({"valid": True, "path": path}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"valid": False, "path": path, "error": str(e)}))]

    async def _merge_toml(self, paths: list[str]) -> list[TextContent]:
        merged: dict[str, Any] = {}
        for p in paths:
            data = self._read_toml(p)
            merged = self._deep_merge(merged, data)
        return [TextContent(type="text", text=json.dumps(merged, indent=2))]

    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = base.copy()
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    async def _format_toml(self, path: str) -> list[TextContent]:
        data = self._read_toml(path)
        self._write_toml(path, data)
        return [TextContent(type="text", text=json.dumps({"formatted": True, "path": path}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = TomlServer()
    async with stdio_server() as (read, write):
        await server.run(
            read, write, server.list_tools, server.call_tool,
            server.list_resources, server.read_resource,
        )

if __name__ == "__main__":
    anyio.run(main)
