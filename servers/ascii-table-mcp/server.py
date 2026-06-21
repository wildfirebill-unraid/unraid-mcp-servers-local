import json
import csv
import io

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
from tabulate import tabulate


class AsciiTableServer(Server):
    VALID_FORMATS = ["grid", "pipe", "simple", "plain", "github", "fancy_grid", "html",
                     "latex", "latex_raw", "latex_booktabs", "orgtbl", "textile",
                     "moinmoin", "youtrack", "mediawiki", "jira", "presto",
                     "pretty", "psql", "rounded_grid", "heavy_grid", "mixed_grid",
                     "double_grid", "outline", "simple_outline", "heavy_outline",
                     "rounded_outline", "double_outline", "asciidoc"]

    def __init__(self):
        super().__init__("ascii-table")

    def _resolve_fmt(self, fmt: str) -> str:
        if not fmt or fmt == "auto":
            return "grid"
        if fmt in self.VALID_FORMATS:
            return fmt
        raise ValueError(f"Unsupported format: {fmt}. Choose from: {', '.join(self.VALID_FORMATS)}")

    def _parse_data(self, data_json: str) -> list:
        data = json.loads(data_json)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
        raise ValueError("data_json must be a JSON array or object")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="from_data", description="Create ASCII table from 2D array or list of dicts",
                 inputSchema={"type": "object", "properties": {
                     "data_json": {"type": "string", "description": "JSON 2D array or list of objects"},
                     "headers_json": {"type": "string", "description": "Optional JSON array of column headers"},
                     "tablefmt": {"type": "string", "description": "Table format (grid/pipe/simple/plain)", "default": "grid"}
                 }, "required": ["data_json"]}),
            Tool(name="from_csv", description="Create ASCII table from CSV text",
                 inputSchema={"type": "object", "properties": {
                     "csv_text": {"type": "string", "description": "CSV formatted text"},
                     "tablefmt": {"type": "string", "description": "Table format", "default": "grid"}
                 }, "required": ["csv_text"]}),
            Tool(name="from_json", description="Create ASCII table from JSON array of objects",
                 inputSchema={"type": "object", "properties": {
                     "json_text": {"type": "string", "description": "JSON array of objects"},
                     "tablefmt": {"type": "string", "description": "Table format", "default": "grid"}
                 }, "required": ["json_text"]}),
            Tool(name="table_info", description="Analyze table data: rows, columns, data types",
                 inputSchema={"type": "object", "properties": {
                     "data_json": {"type": "string", "description": "JSON 2D array or list of objects"}
                 }, "required": ["data_json"]}),
            Tool(name="to_markdown", description="Convert table data to markdown format",
                 inputSchema={"type": "object", "properties": {
                     "data_json": {"type": "string", "description": "JSON 2D array or list of objects"},
                     "headers_json": {"type": "string", "description": "Optional JSON array of column headers"}
                 }, "required": ["data_json"]}),
            Tool(name="merge_tables", description="Merge two tables vertically or horizontally",
                 inputSchema={"type": "object", "properties": {
                     "orientation": {"type": "string", "description": "vertical or horizontal", "enum": ["vertical", "horizontal"]},
                     "tables_json": {"type": "string", "description": "JSON array of two table arrays"}
                 }, "required": ["orientation", "tables_json"]}),
            Tool(name="transpose_table", description="Transpose rows and columns of a table",
                 inputSchema={"type": "object", "properties": {
                     "data_json": {"type": "string", "description": "JSON 2D array"},
                     "headers_json": {"type": "string", "description": "Optional JSON array of column headers"}
                 }, "required": ["data_json"]}),
            Tool(name="style_table", description="Re-render table in a different format",
                 inputSchema={"type": "object", "properties": {
                     "data_json": {"type": "string", "description": "JSON 2D array or list of objects"},
                     "headers_json": {"type": "string", "description": "Optional JSON array of column headers"},
                     "fmt": {"type": "string", "description": "Table format to apply (grid/pipe/simple/plain/etc)"}
                 }, "required": ["data_json", "fmt"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "from_data":
                data = self._parse_data(args["data_json"])
                headers = json.loads(args.get("headers_json", "null"))
                fmt = self._resolve_fmt(args.get("tablefmt", "grid"))
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    result = tabulate(data, headers="keys", tablefmt=fmt)
                else:
                    result = tabulate(data, headers=headers, tablefmt=fmt)
                return [TextContent(type="text", text=result)]

            if name == "from_csv":
                reader = csv.reader(io.StringIO(args["csv_text"]))
                rows = list(reader)
                fmt = self._resolve_fmt(args.get("tablefmt", "grid"))
                if rows:
                    result = tabulate(rows[1:], headers=rows[0], tablefmt=fmt)
                else:
                    result = ""
                return [TextContent(type="text", text=result)]

            if name == "from_json":
                data = json.loads(args["json_text"])
                if not isinstance(data, list):
                    raise ValueError("json_text must be a JSON array")
                fmt = self._resolve_fmt(args.get("tablefmt", "grid"))
                result = tabulate(data, headers="keys", tablefmt=fmt)
                return [TextContent(type="text", text=result)]

            if name == "table_info":
                data = self._parse_data(args["data_json"])
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    keys = list(data[0].keys())
                    col_types = {}
                    for k in keys:
                        types_set = set(type(row.get(k)).__name__ for row in data if k in row)
                        col_types[k] = ", ".join(sorted(types_set)) if types_set else "null"
                    info = json.dumps({"rows": len(data), "columns": len(keys), "column_names": keys, "column_types": col_types}, indent=2)
                elif isinstance(data, list) and data and isinstance(data[0], list):
                    ncols = max(len(r) for r in data) if data else 0
                    info = json.dumps({"rows": len(data), "columns": ncols}, indent=2)
                else:
                    info = json.dumps({"rows": len(data) if isinstance(data, list) else 1, "columns": 0}, indent=2)
                return [TextContent(type="text", text=info)]

            if name == "to_markdown":
                data = self._parse_data(args["data_json"])
                headers = json.loads(args.get("headers_json", "null"))
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    result = tabulate(data, headers="keys", tablefmt="github")
                else:
                    result = tabulate(data, headers=headers, tablefmt="github")
                return [TextContent(type="text", text=result)]

            if name == "merge_tables":
                tables = json.loads(args["tables_json"])
                if not isinstance(tables, list) or len(tables) != 2:
                    raise ValueError("tables_json must be a JSON array of exactly two tables")
                orientation = args["orientation"]
                t1, t2 = tables[0], tables[1]
                if orientation == "vertical":
                    if t1 and t2 and isinstance(t1[0], list) and isinstance(t2[0], list):
                        merged = t1 + t2
                    else:
                        merged = t1 + t2
                elif orientation == "horizontal":
                    if not isinstance(t1, list) or not isinstance(t2, list):
                        raise ValueError("Tables must be arrays for horizontal merge")
                    from itertools import zip_longest
                    merged = [a + b for a, b in zip_longest(t1, t2, fillvalue=[])]
                else:
                    raise ValueError("orientation must be 'vertical' or 'horizontal'")
                return [TextContent(type="text", text=json.dumps(merged))]

            if name == "transpose_table":
                data = json.loads(args["data_json"])
                headers = json.loads(args.get("headers_json", "null"))
                if not isinstance(data, list) or not data:
                    raise ValueError("data_json must be a non-empty 2D array")
                transposed = list(map(list, zip(*data)))
                result = json.dumps({"data": transposed, "headers": headers[::-1] if headers else None})
                return [TextContent(type="text", text=result)]

            if name == "style_table":
                data = self._parse_data(args["data_json"])
                headers = json.loads(args.get("headers_json", "null"))
                fmt = self._resolve_fmt(args["fmt"])
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    result = tabulate(data, headers="keys", tablefmt=fmt)
                else:
                    result = tabulate(data, headers=headers, tablefmt=fmt)
                return [TextContent(type="text", text=result)]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = AsciiTableServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
