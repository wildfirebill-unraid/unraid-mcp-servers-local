import os
import json
import re
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("template-mcp")

BASE_PATH = Path(os.environ.get("TEMPLATE_PATH", "/data"))

def _extract_variables(template: str) -> list[str]:
    pattern = r"\{\{(.*?)\}\}"
    matches = re.findall(pattern, template)
    variables = []
    for m in matches:
        var = m.strip().split(".")[0].split("|")[0].strip()
        if var and var not in variables:
            variables.append(var)
    return variables

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="render_template",
            description="Render a Jinja2 template string with variables",
            inputSchema={
                "type": "object",
                "properties": {
                    "template": {"type": "string", "description": "Template string with {{ }} placeholders"},
                    "variables": {"type": "object", "description": "Dict of variable values"},
                },
                "required": ["template", "variables"],
            },
        ),
        Tool(
            name="render_template_file",
            description="Render a template file with variables",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to template file"},
                    "variables": {"type": "object", "description": "Dict of variable values"},
                    "output": {"type": "string", "description": "Output path (optional)"},
                },
                "required": ["path", "variables"],
            },
        ),
        Tool(
            name="list_variables",
            description="Extract all variable names from a template",
            inputSchema={
                "type": "object",
                "properties": {
                    "template": {"type": "string", "description": "Template string"},
                },
                "required": ["template"],
            },
        ),
        Tool(
            name="validate_template",
            description="Validate template syntax",
            inputSchema={
                "type": "object",
                "properties": {
                    "template": {"type": "string", "description": "Template string"},
                },
                "required": ["template"],
            },
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "render_template":
        template_str = arguments["template"]
        variables = arguments["variables"]
        from jinja2 import Template
        try:
            tmpl = Template(template_str)
            rendered = tmpl.render(**variables)
            result = json.dumps({"rendered": rendered}, indent=2)
        except Exception as e:
            result = json.dumps({"error": str(e)}, indent=2)

    elif name == "render_template_file":
        path = _resolve_path(arguments["path"])
        variables = arguments["variables"]
        output = arguments.get("output")
        from jinja2 import Template
        try:
            with open(path, encoding="utf-8") as f:
                template_str = f.read()
            tmpl = Template(template_str)
            rendered = tmpl.render(**variables)
            if output:
                out_path = _resolve_path(output)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(rendered)
                result = json.dumps({"rendered": True, "path": str(out_path)}, indent=2)
            else:
                result = json.dumps({"rendered": rendered}, indent=2)
        except Exception as e:
            result = json.dumps({"error": str(e)}, indent=2)

    elif name == "list_variables":
        template_str = arguments["template"]
        variables = _extract_variables(template_str)
        result = json.dumps({"variables": variables}, indent=2)

    elif name == "validate_template":
        template_str = arguments["template"]
        from jinja2 import Template
        try:
            Template(template_str)
            result = json.dumps({"valid": True}, indent=2)
        except Exception as e:
            result = json.dumps({"valid": False, "error": str(e)}, indent=2)

    else:
        result = f"Unknown tool: {name}"

    return [TextContent(type="text", text=result)]

def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return BASE_PATH / p

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="template-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
