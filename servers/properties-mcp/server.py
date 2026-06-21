import json
import os
import re
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


def _resolve_path(p: str) -> str:
    base = os.environ.get("PROPERTIES_PATH", "")
    resolved = os.path.abspath(os.path.join(base, p))
    if base:
        real_base = os.path.realpath(base)
        real_resolved = os.path.realpath(resolved)
        if not real_resolved.startswith(real_base.rstrip("\\/") + os.sep) and real_resolved != real_base:
            raise PermissionError(f"Path {p} resolves outside allowed PROPERTIES_PATH ({real_base})")
    return resolved


def _parse_properties_text(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("!"):
            continue
        if "=" in stripped:
            key, _, val = stripped.partition("=")
        elif ":" in stripped:
            key, _, val = stripped.partition(":")
        else:
            continue
        key = key.strip()
        val = val.strip()
        escaped = []
        i = 0
        while i < len(val):
            if val[i] == "\\" and i + 1 < len(val):
                if val[i + 1] == "n":
                    escaped.append("\n")
                elif val[i + 1] == "t":
                    escaped.append("\t")
                elif val[i + 1] == "r":
                    escaped.append("\r")
                else:
                    escaped.append(val[i + 1])
                i += 2
            else:
                escaped.append(val[i])
                i += 1
        result[key] = "".join(escaped)
    return result


def _write_properties_text(data: dict[str, str]) -> str:
    lines = []
    for k, v in data.items():
        val = v.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        lines.append(f"{k}={val}")
    return "\n".join(lines) + "\n" if lines else ""


def _read_properties(path: str) -> dict[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        return _parse_properties_text(f.read())


def _write_properties(path: str, data: dict[str, str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(_write_properties_text(data))


class PropertiesServer(Server):
    def __init__(self):
        super().__init__("properties")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="parse_properties", description="Parse a .properties file and return all key-value pairs", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .properties file"}}, "required": ["path"]}),
            Tool(name="get_value", description="Get a value by key from a .properties file", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .properties file"}, "key": {"type": "string", "description": "Property key"}}, "required": ["path", "key"]}),
            Tool(name="set_value", description="Set a key-value pair in a .properties file and save", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .properties file"}, "key": {"type": "string", "description": "Property key"}, "value": {"type": "string", "description": "Property value"}}, "required": ["path", "key", "value"]}),
            Tool(name="properties_to_json", description="Convert a .properties file to JSON", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .properties file"}}, "required": ["path"]}),
            Tool(name="json_to_properties", description="Create a .properties file from a JSON object", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to create the .properties file at"}, "json_str": {"type": "object", "description": "JSON object with key-value string pairs", "additionalProperties": {"type": "string"}}}, "required": ["path", "json_str"]}),
            Tool(name="list_keys", description="List all keys in a .properties file", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the .properties file"}}, "required": ["path"]}),
            Tool(name="merge_properties", description="Merge multiple .properties files into one (later files override earlier)", inputSchema={"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}, "description": "Array of paths to .properties files"}}, "required": ["paths"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "parse_properties":
                path = _resolve_path(args["path"])
                data = _read_properties(path)
                return [TextContent(type="text", text=json.dumps(data, indent=2))]
            elif name == "get_value":
                path = _resolve_path(args["path"])
                data = _read_properties(path)
                val = data.get(args["key"])
                if val is None:
                    return [TextContent(type="text", text=json.dumps({"error": f"Key '{args['key']}' not found"}))]
                return [TextContent(type="text", text=json.dumps({"key": args["key"], "value": val}))]
            elif name == "set_value":
                path = _resolve_path(args["path"])
                data = _read_properties(path)
                data[args["key"]] = args["value"]
                _write_properties(path, data)
                return [TextContent(type="text", text=json.dumps({"status": "ok", "key": args["key"], "value": args["value"]}))]
            elif name == "properties_to_json":
                path = _resolve_path(args["path"])
                data = _read_properties(path)
                return [TextContent(type="text", text=json.dumps(data, indent=2))]
            elif name == "json_to_properties":
                path = _resolve_path(args["path"])
                data = {k: str(v) for k, v in args["json_str"].items()}
                _write_properties(path, data)
                return [TextContent(type="text", text=json.dumps({"status": "created", "path": path, "count": len(data)}))]
            elif name == "list_keys":
                path = _resolve_path(args["path"])
                data = _read_properties(path)
                return [TextContent(type="text", text=json.dumps({"keys": list(data.keys())}))]
            elif name == "merge_properties":
                merged: dict[str, str] = {}
                for p in args["paths"]:
                    rp = _resolve_path(p)
                    part = _read_properties(rp)
                    merged.update(part)
                return [TextContent(type="text", text=json.dumps(merged, indent=2))]
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = PropertiesServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
