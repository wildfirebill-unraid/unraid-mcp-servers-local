import os
import csv
import json
from pathlib import Path
from io import StringIO
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("csv-mcp")

BASE_PATH = Path(os.environ.get("CSV_PATH", "/data"))

def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return BASE_PATH / p

def _load_csv(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return fieldnames, rows

def _infer_types(rows: list[dict]) -> dict:
    types = {}
    if not rows:
        return types
    for col in rows[0]:
        numeric = 0
        for row in rows:
            v = row.get(col, "").strip()
            if v:
                try:
                    float(v)
                    numeric += 1
                except ValueError:
                    pass
        if numeric == sum(1 for r in rows if r.get(col, "").strip()):
            types[col] = "numeric"
        else:
            types[col] = "string"
    return types

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="csv_query",
            description="Query CSV with filter conditions",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to CSV file"},
                    "columns": {"type": "array", "items": {"type": "string"}, "description": "Columns to select"},
                    "filters": {"type": "object", "description": "Dict of col=value filters"},
                    "limit": {"type": "integer", "description": "Max rows"},
                    "offset": {"type": "integer", "description": "Row offset"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="csv_aggregate",
            description="Aggregate CSV data",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to CSV file"},
                    "group_by": {"type": "string", "description": "Column to group by"},
                    "aggregate": {"type": "string", "enum": ["sum", "count", "avg", "min", "max"], "description": "Aggregation function"},
                    "value_column": {"type": "string", "description": "Column to aggregate"},
                },
                "required": ["path", "group_by", "aggregate", "value_column"],
            },
        ),
        Tool(
            name="csv_sort",
            description="Sort CSV by column",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to CSV file"},
                    "sort_by": {"type": "string", "description": "Column to sort by"},
                    "ascending": {"type": "boolean", "description": "Sort ascending", "default": True},
                    "output": {"type": "string", "description": "Output path"},
                },
                "required": ["path", "sort_by"],
            },
        ),
        Tool(
            name="csv_merge",
            description="Merge multiple CSV files (stack rows)",
            inputSchema={
                "type": "object",
                "properties": {
                    "paths": {"type": "array", "items": {"type": "string"}, "description": "List of CSV paths"},
                    "output": {"type": "string", "description": "Output path"},
                },
                "required": ["paths", "output"],
            },
        ),
        Tool(
            name="csv_stats",
            description="Get basic statistics about CSV file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to CSV file"},
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="csv_join",
            description="Join two CSV files on a column",
            inputSchema={
                "type": "object",
                "properties": {
                    "path1": {"type": "string", "description": "First CSV path"},
                    "path2": {"type": "string", "description": "Second CSV path"},
                    "on": {"type": "string", "description": "Column to join on"},
                    "how": {"type": "string", "enum": ["inner", "left", "right", "outer"], "description": "Join type", "default": "inner"},
                    "output": {"type": "string", "description": "Output path"},
                },
                "required": ["path1", "path2", "on", "output"],
            },
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "csv_query":
        path = _resolve_path(arguments["path"])
        fieldnames, rows = _load_csv(path)
        cols = arguments.get("columns")
        filters = arguments.get("filters", {})
        limit = arguments.get("limit")
        offset = arguments.get("offset", 0)

        result_rows = []
        for row in rows:
            match = True
            for k, v in filters.items():
                if row.get(k, "").strip() != str(v).strip():
                    match = False
                    break
            if match:
                result_rows.append(row)

        result_rows = result_rows[offset:]
        if limit is not None:
            result_rows = result_rows[:limit]

        if cols:
            selected = []
            for row in result_rows:
                selected.append({k: row.get(k, "") for k in cols if k in row})
            result_rows = selected

        result = json.dumps(result_rows, indent=2)

    elif name == "csv_aggregate":
        path = _resolve_path(arguments["path"])
        group_by = arguments["group_by"]
        agg = arguments["aggregate"]
        val_col = arguments["value_column"]
        fieldnames, rows = _load_csv(path)

        groups = {}
        for row in rows:
            key = row.get(group_by, "")
            if key not in groups:
                groups[key] = []
            try:
                groups[key].append(float(row.get(val_col, 0)))
            except ValueError:
                pass

        result_rows = []
        for key, vals in groups.items():
            if not vals:
                continue
            if agg == "count":
                res = len(vals)
            elif agg == "sum":
                res = sum(vals)
            elif agg == "avg":
                res = sum(vals) / len(vals)
            elif agg == "min":
                res = min(vals)
            elif agg == "max":
                res = max(vals)
            else:
                res = 0
            result_rows.append({group_by: key, f"{agg}_{val_col}": res})

        result = json.dumps(result_rows, indent=2)

    elif name == "csv_sort":
        path = _resolve_path(arguments["path"])
        sort_by = arguments["sort_by"]
        ascending = arguments.get("ascending", True)
        output = arguments.get("output")

        fieldnames, rows = _load_csv(path)
        rows.sort(key=lambda r: r.get(sort_by, ""), reverse=not ascending)

        out_path = _resolve_path(output) if output else path
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        result = json.dumps({"sorted": True, "path": str(out_path), "rows": len(rows)}, indent=2)

    elif name == "csv_merge":
        paths = arguments["paths"]
        output = _resolve_path(arguments["output"])
        all_rows = []
        all_fields = []
        for p in paths:
            fp = _resolve_path(p)
            fn, rows = _load_csv(fp)
            all_rows.extend(rows)
            for f in fn:
                if f not in all_fields:
                    all_fields.append(f)

        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_rows)

        result = json.dumps({"merged": True, "path": str(output), "total_rows": len(all_rows)}, indent=2)

    elif name == "csv_stats":
        path = _resolve_path(arguments["path"])
        fieldnames, rows = _load_csv(path)
        types = _infer_types(rows)
        result = json.dumps({
            "row_count": len(rows),
            "column_names": fieldnames,
            "column_types": types,
        }, indent=2)

    elif name == "csv_join":
        path1 = _resolve_path(arguments["path1"])
        path2 = _resolve_path(arguments["path2"])
        on = arguments["on"]
        how = arguments.get("how", "inner")
        output = _resolve_path(arguments["output"])

        fn1, rows1 = _load_csv(path1)
        fn2, rows2 = _load_csv(path2)

        lookup = {}
        for row in rows2:
            key = row.get(on, "")
            if key not in lookup:
                lookup[key] = []
            lookup[key].append(row)

        all_fields = list(dict.fromkeys(fn1 + fn2))
        joined = []

        keys1 = set(r.get(on, "") for r in rows1)
        keys2 = set(r.get(on, "") for r in rows2)

        for row1 in rows1:
            key = row1.get(on, "")
            matches = lookup.get(key, [])
            if how in ("inner", "left") and not matches and how == "left":
                merged = dict(row1)
                for f in fn2:
                    if f != on:
                        merged[f] = ""
                joined.append(merged)
            for row2 in matches:
                merged = dict(row1)
                merged.update(row2)
                joined.append(merged)

        if how in ("right", "outer"):
            for row2 in rows2:
                key = row2.get(on, "")
                if key not in keys1:
                    merged = {}
                    for f in all_fields:
                        merged[f] = ""
                    merged.update(row2)
                    joined.append(merged)

        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(joined)

        result = json.dumps({"joined": True, "path": str(output), "rows": len(joined)}, indent=2)

    else:
        result = f"Unknown tool: {name}"

    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="csv-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
