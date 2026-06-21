import json
import os
import re
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


def _resolve_path(p: str) -> str:
    base = os.environ.get("ENVFILE_PATH", "")
    resolved = os.path.abspath(os.path.join(base, p))
    if base:
        real_base = os.path.realpath(base)
        real_resolved = os.path.realpath(resolved)
        if not real_resolved.startswith(real_base.rstrip("\\/") + os.sep) and real_resolved != real_base:
            raise PermissionError(f"Path {p} resolves outside allowed ENVFILE_PATH ({real_base})")
    return resolved


_LINE_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def _parse_env_text(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = _LINE_RE.match(stripped)
        if not m:
            continue
        key = m.group(1)
        val = m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
            val = val.replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")
        result[key] = val
    return result


def _write_env_text(data: dict[str, str], sort: bool = False) -> str:
    keys = sorted(data) if sort else list(data)
    lines = []
    for k in keys:
        v = data[k]
        if any(c in v for c in (" ", "#", "'", '"', "\\")):
            escaped = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
            lines.append(f'{k}="{escaped}"')
        else:
            lines.append(f"{k}={v}")
    return "\n".join(lines) + "\n" if lines else ""


def _read_env(path: str) -> dict[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        return _parse_env_text(f.read())


def _write_env(path: str, data: dict[str, str], sort: bool = False) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(_write_env_text(data, sort=sort))


class EnvfileServer(Server):
    def __init__(self):
        super().__init__("envfile")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="parse_env", description="Parse a .env file and return all key-value pairs", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .env file"}}, "required": ["path"]}),
            Tool(name="get_env_var", description="Get a specific environment variable value from a .env file", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .env file"}, "key": {"type": "string", "description": "Variable name"}}, "required": ["path", "key"]}),
            Tool(name="set_env_var", description="Set an environment variable in a .env file and save", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .env file"}, "key": {"type": "string", "description": "Variable name"}, "value": {"type": "string", "description": "Variable value"}}, "required": ["path", "key", "value"]}),
            Tool(name="remove_env_var", description="Remove an environment variable from a .env file", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .env file"}, "key": {"type": "string", "description": "Variable name to remove"}}, "required": ["path", "key"]}),
            Tool(name="validate_env", description="Check that required keys exist in a .env file", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .env file"}, "required_keys": {"type": "array", "items": {"type": "string"}, "description": "List of required variable names"}}, "required": ["path", "required_keys"]}),
            Tool(name="env_to_json", description="Convert a .env file to JSON", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .env file"}}, "required": ["path"]}),
            Tool(name="merge_env", description="Merge multiple .env files into one (later files override earlier)", inputSchema={"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}, "description": "Array of paths to .env files"}}, "required": ["paths"]}),
            Tool(name="format_env", description="Reformat a .env file with consistent spacing and optional sorting", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .env file"}, "sort": {"type": "boolean", "description": "Sort keys alphabetically", "default": False}}, "required": ["path"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "parse_env":
                path = _resolve_path(args["path"])
                data = _read_env(path)
                return [TextContent(type="text", text=json.dumps(data, indent=2))]
            elif name == "get_env_var":
                path = _resolve_path(args["path"])
                data = _read_env(path)
                val = data.get(args["key"])
                if val is None:
                    return [TextContent(type="text", text=json.dumps({"error": f"Variable '{args['key']}' not found"}))]
                return [TextContent(type="text", text=json.dumps({"key": args["key"], "value": val}))]
            elif name == "set_env_var":
                path = _resolve_path(args["path"])
                data = _read_env(path)
                data[args["key"]] = args["value"]
                _write_env(path, data)
                return [TextContent(type="text", text=json.dumps({"status": "ok", "key": args["key"], "value": args["value"]}))]
            elif name == "remove_env_var":
                path = _resolve_path(args["path"])
                data = _read_env(path)
                if args["key"] not in data:
                    return [TextContent(type="text", text=json.dumps({"error": f"Variable '{args['key']}' not found"}))]
                del data[args["key"]]
                _write_env(path, data)
                return [TextContent(type="text", text=json.dumps({"status": "removed", "key": args["key"]}))]
            elif name == "validate_env":
                path = _resolve_path(args["path"])
                data = _read_env(path)
                missing = [k for k in args["required_keys"] if k not in data]
                if missing:
                    return [TextContent(type="text", text=json.dumps({"valid": False, "missing": missing}))]
                return [TextContent(type="text", text=json.dumps({"valid": True, "missing": []}))]
            elif name == "env_to_json":
                path = _resolve_path(args["path"])
                data = _read_env(path)
                return [TextContent(type="text", text=json.dumps(data, indent=2))]
            elif name == "merge_env":
                merged: dict[str, str] = {}
                for p in args["paths"]:
                    rp = _resolve_path(p)
                    part = _read_env(rp)
                    merged.update(part)
                return [TextContent(type="text", text=json.dumps(merged, indent=2))]
            elif name == "format_env":
                path = _resolve_path(args["path"])
                data = _read_env(path)
                do_sort = args.get("sort", False)
                _write_env(path, data, sort=do_sort)
                return [TextContent(type="text", text=json.dumps({"status": "formatted", "path": path, "sort": do_sort}))]
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = EnvfileServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
