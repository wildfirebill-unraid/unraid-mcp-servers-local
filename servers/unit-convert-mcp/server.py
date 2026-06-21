import json

import pint

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

UREG = pint.UnitRegistry()
UREG.formatter.default_format = "~P"


def _category_for(unit_str: str) -> str | None:
    try:
        u = UREG.Unit(unit_str)
        dim = u.dimensionality
        return str(dim) if dim else None
    except Exception:
        return None


def _get_all_categories() -> list[dict]:
    seen = {}
    for name in dir(UREG.sys):
        if not name.startswith("_"):
            cat = _category_for(name)
            if cat and cat not in seen:
                seen[cat] = {"name": cat}
    return list(seen.values())


def _get_units_for_category(category: str) -> list[str]:
    units = []
    for name in dir(UREG.sys):
        if not name.startswith("_") and not name.startswith("["):
            try:
                u = UREG.Unit(name)
                if str(u.dimensionality) == category:
                    units.append(name)
            except Exception:
                pass
    return sorted(units)


def _parse_unit_safe(unit_str: str) -> pint.Unit:
    try:
        return UREG.Unit(unit_str)
    except Exception:
        raise ValueError(f"Unknown unit: '{unit_str}'")


class UnitConvertServer(Server):
    def __init__(self):
        super().__init__("unit-convert")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="convert", description="Convert a value between units",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "value": {"type": "number", "description": "Numeric value to convert"},
                         "from_unit": {"type": "string", "description": "Source unit e.g. 'meter', 'foot', 'celsius'"},
                         "to_unit": {"type": "string", "description": "Target unit e.g. 'kilometer', 'inch', 'fahrenheit'"}
                     },
                     "required": ["value", "from_unit", "to_unit"]
                 }),
            Tool(name="list_categories", description="List all measurement categories",
                 inputSchema={
                     "type": "object",
                     "properties": {}
                 }),
            Tool(name="list_units", description="List all units in a measurement category",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "category": {"type": "string", "description": "Category name e.g. '[length]', '[mass]', '[temperature]'"}
                     },
                     "required": ["category"]
                 }),
            Tool(name="list_compatible", description="List all units compatible with a given unit",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "unit": {"type": "string", "description": "Unit to find compatibles for e.g. 'meter'"}
                     },
                     "required": ["unit"]
                 }),
            Tool(name="unit_info", description="Show definition and info for a unit",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "unit": {"type": "string", "description": "Unit name e.g. 'meter', 'N', 'atm'"}
                     },
                     "required": ["unit"]
                 }),
            Tool(name="convert_batch", description="Batch convert multiple values",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "conversions_json": {"type": "string", "description": "JSON array of {value, from, to} objects"}
                     },
                     "required": ["conversions_json"]
                 }),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "convert":
                value = float(args["value"])
                src = _parse_unit_safe(args["from_unit"])
                dst = _parse_unit_safe(args["to_unit"])
                result = (value * src).to(dst).magnitude
                return [TextContent(type="text", text=json.dumps({
                    "value": value,
                    "from": args["from_unit"],
                    "to": args["to_unit"],
                    "result": result
                }))]

            elif name == "list_categories":
                categories = _get_all_categories()
                return [TextContent(type="text", text=json.dumps({"categories": categories}))]

            elif name == "list_units":
                units = _get_units_for_category(args["category"])
                return [TextContent(type="text", text=json.dumps({
                    "category": args["category"],
                    "units": units
                }))]

            elif name == "list_compatible":
                u = _parse_unit_safe(args["unit"])
                dim = u.dimensionality
                compat = _get_units_for_category(str(dim))
                return [TextContent(type="text", text=json.dumps({
                    "unit": args["unit"],
                    "dimensionality": str(dim),
                    "compatible_units": compat
                }))]

            elif name == "unit_info":
                u = _parse_unit_safe(args["unit"])
                compat = []
                for name_ in dir(UREG.sys):
                    if not name_.startswith("_") and not name_.startswith("["):
                        try:
                            if UREG.Unit(name_).is_compatible_with(u):
                                compat.append(name_)
                        except Exception:
                            pass
                return [TextContent(type="text", text=json.dumps({
                    "unit": args["unit"],
                    "canonical_name": str(u),
                    "dimensionality": str(u.dimensionality),
                    "aliases": sorted(compat[:20]),
                    "is_base": u.is_base()
                }))]

            elif name == "convert_batch":
                conversions = json.loads(args["conversions_json"])
                results = []
                for item in conversions:
                    try:
                        val = float(item["value"])
                        src = _parse_unit_safe(item["from"])
                        dst = _parse_unit_safe(item["to"])
                        res = (val * src).to(dst).magnitude
                        results.append({
                            "value": val,
                            "from": item["from"],
                            "to": item["to"],
                            "result": res
                        })
                    except Exception as e:
                        results.append({
                            "value": item.get("value"),
                            "from": item.get("from"),
                            "to": item.get("to"),
                            "error": str(e)
                        })
                return [TextContent(type="text", text=json.dumps({"conversions": results}))]

            else:
                raise ValueError(f"Unknown tool: {name}")

        except json.JSONDecodeError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Invalid JSON: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = UnitConvertServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
