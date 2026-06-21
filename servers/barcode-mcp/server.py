import json
import os
from pathlib import Path

from barcode import EAN13, Code128, Code39, ISBN13, UPCA, PROVIDED_BARCODES, get_barcode_class
from barcode.writer import SVGWriter
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


SYMBOLOGY_INFO = {
    "ean": "European Article Number - 13-digit standard barcode",
    "ean13": "EAN-13 - 13-digit product barcode",
    "ean8": "EAN-8 - 8-digit product barcode for small packages",
    "gs1": "GS1-128 - Supply chain standard barcode",
    "gs1_128": "GS1-128 - Supply chain standard barcode",
    "gtin": "Global Trade Item Number barcode",
    "isbn": "International Standard Book Number (13-digit)",
    "isbn13": "ISBN-13 - 13-digit book identifier",
    "isbn10": "ISBN-10 - 10-digit book identifier (legacy)",
    "issn": "International Standard Serial Number",
    "jan": "Japanese Article Number barcode",
    "pzn": "Pharmazentralnummer - German pharmaceutical barcode",
    "upc": "Universal Product Code (12-digit)",
    "upca": "UPC-A - 12-digit retail product barcode",
}


class BarcodeServer(Server):
    def __init__(self):
        super().__init__("barcode")
        self._init_env()

    def _init_env(self):
        self._output_path = os.environ.get("BARCODE_PATH", os.path.join(os.getcwd(), "barcodes"))
        Path(self._output_path).mkdir(parents=True, exist_ok=True)

    def _save_barcode(self, barcode_class, data: str, prefix: str) -> str:
        writer = SVGWriter()
        code = barcode_class(data, writer=writer)
        safe = "".join(c if c.isalnum() else "_" for c in data)[:20]
        filepath = os.path.join(self._output_path, f"{prefix}_{safe}")
        saved = code.save(filepath)
        return saved

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="generate_ean13",
                description="Generate an EAN-13 barcode (12 digits, 13th check digit computed)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "12-digit EAN code (check digit will be computed)"},
                    },
                    "required": ["data"],
                },
            ),
            Tool(
                name="generate_code128",
                description="Generate a Code128 barcode",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "Data to encode in Code128 format"},
                    },
                    "required": ["data"],
                },
            ),
            Tool(
                name="generate_code39",
                description="Generate a Code39 barcode",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "Data to encode in Code39 format (alphanumeric)"},
                    },
                    "required": ["data"],
                },
            ),
            Tool(
                name="generate_isbn",
                description="Generate an ISBN-13 barcode (12 digits)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "12-digit ISBN (check digit computed automatically)"},
                    },
                    "required": ["data"],
                },
            ),
            Tool(
                name="generate_upc",
                description="Generate a UPC-A barcode (11 digits, 12th check digit computed)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "11-digit UPC code (check digit will be computed)"},
                    },
                    "required": ["data"],
                },
            ),
            Tool(
                name="list_symbologies",
                description="List all supported barcode symbologies",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="barcode_info",
                description="Get information about a barcode type",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Barcode symbology name (e.g. ean13, code128, upca)"},
                    },
                    "required": ["type"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "generate_ean13":
                path = self._save_barcode(EAN13, args["data"], "ean13")
                return [TextContent(type="text", text=json.dumps({"path": path}))]
            if name == "generate_code128":
                path = self._save_barcode(Code128, args["data"], "code128")
                return [TextContent(type="text", text=json.dumps({"path": path}))]
            if name == "generate_code39":
                path = self._save_barcode(Code39, args["data"], "code39")
                return [TextContent(type="text", text=json.dumps({"path": path}))]
            if name == "generate_isbn":
                path = self._save_barcode(ISBN13, args["data"], "isbn")
                return [TextContent(type="text", text=json.dumps({"path": path}))]
            if name == "generate_upc":
                path = self._save_barcode(UPCA, args["data"], "upc")
                return [TextContent(type="text", text=json.dumps({"path": path}))]
            if name == "list_symbologies":
                return [TextContent(type="text", text=json.dumps({"symbologies": list(PROVIDED_BARCODES)}))]
            if name == "barcode_info":
                btype = args["type"].lower()
                desc = SYMBOLOGY_INFO.get(btype, f"No information available for '{btype}'")
                try:
                    cls = get_barcode_class(btype)
                    extra = {"class": cls.__name__}
                except Exception:
                    extra = {"class": None}
                return [TextContent(type="text", text=json.dumps({"type": btype, "description": desc, **extra}))]
            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = BarcodeServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
