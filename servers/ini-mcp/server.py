import json
import os
import configparser
from io import StringIO
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


def _resolve_path(p: str) -> str:
    base = os.environ.get("INI_PATH", "")
    resolved = os.path.abspath(os.path.join(base, p))
    if base:
        real_base = os.path.realpath(base)
        real_resolved = os.path.realpath(resolved)
        if not real_resolved.startswith(real_base.rstrip("\\/") + os.sep) and real_resolved != real_base:
            raise PermissionError(f"Path {p} resolves outside allowed INI_PATH ({real_base})")
    return resolved


def _read_ini(path: str) -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    return cp


def _write_ini(path: str, cp: configparser.ConfigParser) -> None:
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)


def _cp_to_dict(cp: configparser.ConfigParser) -> dict[str, dict[str, str]]:
    return {s: dict(cp.items(s)) for s in cp.sections()}


class IniServer(Server):
    def __init__(self):
        super().__init__("ini")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="parse_ini", description="Parse an INI file and return all sections with their keys and values", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the INI file"}}, "required": ["path"]}),
            Tool(name="get_value", description="Get a specific value from an INI file by section and key", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the INI file"}, "section": {"type": "string", "description": "Section name"}, "key": {"type": "string", "description": "Key name"}}, "required": ["path", "section", "key"]}),
            Tool(name="set_value", description="Set a value in an INI file and save back to disk", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the INI file"}, "section": {"type": "string", "description": "Section name"}, "key": {"type": "string", "description": "Key name"}, "value": {"type": "string", "description": "Value to set"}}, "required": ["path", "section", "key", "value"]}),
            Tool(name="list_sections", description="List all section names in an INI file", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the INI file"}}, "required": ["path"]}),
            Tool(name="list_keys", description="List all keys in a specific section of an INI file", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the INI file"}, "section": {"type": "string", "description": "Section name"}}, "required": ["path", "section"]}),
            Tool(name="create_ini", description="Create a new INI file from a JSON-like dict of sections", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to create the INI file at"}, "content": {"type": "object", "description": "Dict of sections: {section: {key: value}, ...}", "additionalProperties": {"type": "object", "additionalProperties": {"type": "string"}}}}, "required": ["path", "content"]}),
            Tool(name="ini_to_json", description="Convert an INI file to JSON representation", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the INI file"}}, "required": ["path"]}),
            Tool(name="remove_section", description="Remove an entire section from an INI file", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the INI file"}, "section": {"type": "string", "description": "Section name to remove"}}, "required": ["path", "section"]}),
            Tool(name="remove_key", description="Remove a specific key from a section in an INI file", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Path to the INI file"}, "section": {"type": "string", "description": "Section name"}, "key": {"type": "string", "description": "Key name to remove"}}, "required": ["path", "section", "key"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "parse_ini":
                path = _resolve_path(args["path"])
                cp = _read_ini(path)
                return [TextContent(type="text", text=json.dumps(_cp_to_dict(cp), indent=2))]
            elif name == "get_value":
                path = _resolve_path(args["path"])
                cp = _read_ini(path)
                val = cp.get(args["section"], args["key"], fallback=None)
                if val is None:
                    return [TextContent(type="text", text=json.dumps({"error": f"Key '{args['key']}' not found in section '{args['section']}'"}))]
                return [TextContent(type="text", text=json.dumps({"value": val}))]
            elif name == "set_value":
                path = _resolve_path(args["path"])
                cp = _read_ini(path)
                if not cp.has_section(args["section"]):
                    cp.add_section(args["section"])
                cp.set(args["section"], args["key"], args["value"])
                _write_ini(path, cp)
                return [TextContent(type="text", text=json.dumps({"status": "ok", "section": args["section"], "key": args["key"], "value": args["value"]}))]
            elif name == "list_sections":
                path = _resolve_path(args["path"])
                cp = _read_ini(path)
                return [TextContent(type="text", text=json.dumps({"sections": cp.sections()}))]
            elif name == "list_keys":
                path = _resolve_path(args["path"])
                cp = _read_ini(path)
                if not cp.has_section(args["section"]):
                    return [TextContent(type="text", text=json.dumps({"error": f"Section '{args['section']}' not found"}))]
                keys = list(cp[args["section"]].keys())
                return [TextContent(type="text", text=json.dumps({"section": args["section"], "keys": keys}))]
            elif name == "create_ini":
                path = _resolve_path(args["path"])
                cp = configparser.ConfigParser()
                for section, items in args["content"].items():
                    cp[section] = {}
                    for k, v in items.items():
                        cp[section][k] = str(v)
                _write_ini(path, cp)
                return [TextContent(type="text", text=json.dumps({"status": "created", "path": path, "sections": list(args["content"].keys())}))]
            elif name == "ini_to_json":
                path = _resolve_path(args["path"])
                cp = _read_ini(path)
                return [TextContent(type="text", text=json.dumps(_cp_to_dict(cp), indent=2))]
            elif name == "remove_section":
                path = _resolve_path(args["path"])
                cp = _read_ini(path)
                removed = cp.remove_section(args["section"])
                if not removed:
                    return [TextContent(type="text", text=json.dumps({"error": f"Section '{args['section']}' not found"}))]
                _write_ini(path, cp)
                return [TextContent(type="text", text=json.dumps({"status": "removed", "section": args["section"]}))]
            elif name == "remove_key":
                path = _resolve_path(args["path"])
                cp = _read_ini(path)
                if not cp.has_section(args["section"]):
                    return [TextContent(type="text", text=json.dumps({"error": f"Section '{args['section']}' not found"}))]
                removed = cp.remove_option(args["section"], args["key"])
                if not removed:
                    return [TextContent(type="text", text=json.dumps({"error": f"Key '{args['key']}' not found in section '{args['section']}'"}))]
                _write_ini(path, cp)
                return [TextContent(type="text", text=json.dumps({"status": "removed", "section": args["section"], "key": args["key"]}))]
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = IniServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
