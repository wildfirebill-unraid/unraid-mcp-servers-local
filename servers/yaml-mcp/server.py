import os
import json
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio
import yaml

BASE = Path(os.environ.get("YAML_BASE_PATH", "/data"))
server = Server("yaml-mcp")

def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else BASE / path

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="yaml_parse", description="Parse YAML string to JSON", inputSchema={"type": "object", "properties": {"yaml_text": {"type": "string"}}, "required": ["yaml_text"]}),
        Tool(name="yaml_dump", description="Convert JSON to YAML string", inputSchema={"type": "object", "properties": {"json_text": {"type": "string"}, "indent": {"type": "integer", "default": 2}}, "required": ["json_text"]}),
        Tool(name="yaml_validate", description="Validate YAML syntax", inputSchema={"type": "object", "properties": {"yaml_text": {"type": "string"}}, "required": ["yaml_text"]}),
        Tool(name="yaml_to_json", description="Read YAML file and output as JSON", inputSchema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}),
        Tool(name="yaml_merge", description="Deep-merge multiple YAML files", inputSchema={"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}}}, "required": ["paths"]}),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

def deep_merge(base, overlay):
    result = base.copy()
    for k, v in overlay.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "yaml_parse":
        data = yaml.safe_load(arguments["yaml_text"])
        return [TextContent(type="text", text=json.dumps(data, indent=2))]
    elif name == "yaml_dump":
        data = json.loads(arguments["json_text"])
        indent = arguments.get("indent", 2)
        text = yaml.dump(data, indent=indent, default_flow_style=False)
        return [TextContent(type="text", text=text)]
    elif name == "yaml_validate":
        try:
            yaml.safe_load(arguments["yaml_text"])
            return [TextContent(type="text", text=json.dumps({"valid": True}))]
        except yaml.YAMLError as e:
            return [TextContent(type="text", text=json.dumps({"valid": False, "error": str(e)}))]
    elif name == "yaml_to_json":
        path = _resolve(arguments["path"])
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return [TextContent(type="text", text=json.dumps(data, indent=2))]
    elif name == "yaml_merge":
        merged = {}
        for p in arguments["paths"]:
            path = _resolve(p)
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
            merged = deep_merge(merged, data)
        return [TextContent(type="text", text=yaml.dump(merged, indent=2, default_flow_style=False))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationOptions(server_name="yaml-mcp", server_version="1.0.0"),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
