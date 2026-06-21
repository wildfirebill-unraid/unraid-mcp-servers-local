import os
import json
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio
from lxml import etree

BASE = Path(os.environ.get("XML_BASE_PATH", "/data"))
server = Server("xml-mcp")

def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else BASE / path

def _parse_xml(text: str):
    parser = etree.XMLParser(remove_blank_text=True)
    return etree.fromstring(text.encode(), parser)

def _element_to_dict(elem) -> dict:
    result = {"tag": elem.tag, "attrib": dict(elem.attrib), "text": elem.text.strip() if elem.text and elem.text.strip() else None}
    children = [_element_to_dict(c) for c in elem]
    if children:
        result["children"] = children
    return result

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="xml_parse", description="Parse XML string to JSON structure", inputSchema={"type": "object", "properties": {"xml_text": {"type": "string"}}, "required": ["xml_text"]}),
        Tool(name="xml_query", description="Query XML with XPath expression", inputSchema={"type": "object", "properties": {"xml_text": {"type": "string"}, "xpath": {"type": "string"}}, "required": ["xml_text", "xpath"]}),
        Tool(name="xml_to_json", description="Convert XML to JSON", inputSchema={"type": "object", "properties": {"xml_text": {"type": "string"}}, "required": ["xml_text"]}),
        Tool(name="xml_validate", description="Validate XML against XSD schema", inputSchema={"type": "object", "properties": {"xml_text": {"type": "string"}, "xsd_path": {"type": "string"}}, "required": ["xml_text", "xsd_path"]}),
        Tool(name="xml_format", description="Pretty-print XML", inputSchema={"type": "object", "properties": {"xml_text": {"type": "string"}, "indent": {"type": "integer", "default": 2}}, "required": ["xml_text"]}),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "xml_parse":
        root = _parse_xml(arguments["xml_text"])
        return [TextContent(type="text", text=json.dumps(_element_to_dict(root), indent=2))]
    elif name == "xml_query":
        root = _parse_xml(arguments["xml_text"])
        results = root.xpath(arguments["xpath"])
        if isinstance(results, list):
            out = []
            for r in results:
                if hasattr(r, "tag"):
                    out.append(_element_to_dict(r))
                else:
                    out.append(str(r))
            return [TextContent(type="text", text=json.dumps(out, indent=2))]
        return [TextContent(type="text", text=str(results))]
    elif name == "xml_to_json":
        root = _parse_xml(arguments["xml_text"])
        return [TextContent(type="text", text=json.dumps(_element_to_dict(root), indent=2))]
    elif name == "xml_validate":
        xsd_path = _resolve(arguments["xsd_path"])
        xsd_doc = etree.parse(str(xsd_path))
        xsd = etree.XMLSchema(xsd_doc)
        doc = etree.fromstring(arguments["xml_text"].encode())
        valid = xsd.validate(doc)
        errors = [str(e) for e in xsd.error_log] if not valid else []
        return [TextContent(type="text", text=json.dumps({"valid": valid, "errors": errors}))]
    elif name == "xml_format":
        root = _parse_xml(arguments["xml_text"])
        indent = arguments.get("indent", 2)
        s = etree.tostring(root, pretty_print=True, encoding="unicode", xml_declaration=True)
        return [TextContent(type="text", text=s)]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationOptions(server_name="xml-mcp", server_version="1.0.0"),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
