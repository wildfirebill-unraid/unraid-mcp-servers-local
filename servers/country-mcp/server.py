import json
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

import pycountry


def _country_to_dict(c: Any) -> dict:
    result = {}
    for attr in ("alpha_2", "alpha_3", "numeric", "name", "official_name", "common_name"):
        val = getattr(c, attr, None)
        if val is not None:
            result[attr] = val
    return result


class CountryServer(Server):
    def __init__(self):
        super().__init__("country")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="country_info",
                description="Get country details by alpha-2, alpha-3, or numeric code",
                inputSchema={
                    "type": "object",
                    "properties": {"code": {"type": "string", "description": "Alpha-2, alpha-3, or numeric country code"}},
                    "required": ["code"],
                },
            ),
            Tool(
                name="search_country",
                description="Search for a country by name (fuzzy match)",
                inputSchema={
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Country name or partial name to search for"}},
                    "required": ["query"],
                },
            ),
            Tool(
                name="list_countries",
                description="List all countries with their codes",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="list_currencies",
                description="List all currencies",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="list_languages",
                description="List all languages",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="list_subdivisions",
                description="List states/provinces/subdivisions for a country",
                inputSchema={
                    "type": "object",
                    "properties": {"country_code": {"type": "string", "description": "Alpha-2 country code"}},
                    "required": ["country_code"],
                },
            ),
            Tool(
                name="convert_codes",
                description="Convert between country code formats (e.g. alpha-2 to alpha-3)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "The code to convert"},
                        "from_format": {"type": "string", "description": "Source format: alpha2, alpha3, or numeric", "enum": ["alpha2", "alpha3", "numeric"]},
                        "to_format": {"type": "string", "description": "Target format: alpha2, alpha3, or numeric", "enum": ["alpha2", "alpha3", "numeric"]},
                    },
                    "required": ["code", "from_format", "to_format"],
                },
            ),
            Tool(
                name="list_country_codes",
                description="List all countries with their alpha-2, alpha-3, and numeric codes",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}

        try:
            if name == "country_info":
                code = args.get("code", "").strip()
                lookup_map = {}
                if len(code) == 2:
                    lookup_map = {"alpha_2": code.upper()}
                elif len(code) == 3 and code.isdigit():
                    lookup_map = {"numeric": code}
                elif len(code) == 3:
                    lookup_map = {"alpha_3": code.upper()}
                else:
                    lookup_map = {"alpha_2": code.upper()}
                country = pycountry.countries.get(**lookup_map)
                if not country:
                    country = pycountry.countries.lookup(code)
                if not country:
                    return [TextContent(type="text", text=json.dumps({"error": f"Country not found: {code}"}))]
                return [TextContent(type="text", text=json.dumps(_country_to_dict(country)))]

            elif name == "search_country":
                query = args.get("query", "")
                results = []
                for c in pycountry.countries:
                    if query.lower() in c.name.lower() or (hasattr(c, "official_name") and c.official_name and query.lower() in c.official_name.lower()):
                        results.append(_country_to_dict(c))
                return [TextContent(type="text", text=json.dumps({"query": query, "count": len(results), "results": results}))]

            elif name == "list_countries":
                countries = [_country_to_dict(c) for c in pycountry.countries]
                return [TextContent(type="text", text=json.dumps({"count": len(countries), "countries": countries}))]

            elif name == "list_currencies":
                currencies = []
                for c in pycountry.currencies:
                    currencies.append({
                        "code": c.alpha_3,
                        "name": c.name,
                        "numeric": getattr(c, "numeric", None),
                    })
                return [TextContent(type="text", text=json.dumps({"count": len(currencies), "currencies": currencies}))]

            elif name == "list_languages":
                langs = []
                for l in pycountry.languages:
                    entry = {"code": l.alpha_3, "name": l.name}
                    if hasattr(l, "alpha_2") and l.alpha_2:
                        entry["alpha_2"] = l.alpha_2
                    if hasattr(l, "bibliographic") and l.bibliographic:
                        entry["bibliographic"] = l.bibliographic
                    langs.append(entry)
                return [TextContent(type="text", text=json.dumps({"count": len(langs), "languages": langs}))]

            elif name == "list_subdivisions":
                country_code = args.get("country_code", "").upper()
                subs = list(pycountry.subdivisions.get(country_code=country_code))
                if not subs:
                    return [TextContent(type="text", text=json.dumps({"error": f"No subdivisions found for country code: {country_code}"}))]
                subdivisions = [{"code": s.code, "name": s.name, "type": s.type} for s in subs]
                return [TextContent(type="text", text=json.dumps({"country_code": country_code, "count": len(subdivisions), "subdivisions": subdivisions}))]

            elif name == "convert_codes":
                code = args.get("code", "").strip()
                from_fmt = args.get("from_format", "").strip()
                to_fmt = args.get("to_format", "").strip()

                fmt_map = {"alpha2": "alpha_2", "alpha3": "alpha_3", "numeric": "numeric"}
                attr_from = fmt_map.get(from_fmt)
                attr_to = fmt_map.get(to_fmt)
                if not attr_from or not attr_to:
                    return [TextContent(type="text", text=json.dumps({"error": "Invalid format. Use: alpha2, alpha3, or numeric"}))]

                country = None
                if from_fmt == "alpha2":
                    country = pycountry.countries.get(alpha_2=code.upper())
                elif from_fmt == "alpha3":
                    country = pycountry.countries.get(alpha_3=code.upper())
                elif from_fmt == "numeric":
                    country = pycountry.countries.get(numeric=code)

                if not country:
                    return [TextContent(type="text", text=json.dumps({"error": f"Country not found with {from_fmt} code: {code}"}))]

                result = getattr(country, attr_to, None)
                if result is None:
                    return [TextContent(type="text", text=json.dumps({"error": f"Country has no {to_fmt} code"}))]

                return [TextContent(type="text", text=json.dumps({
                    "input": {"code": code, "format": from_fmt},
                    "output": {"code": result, "format": to_fmt},
                    "country": country.name,
                }))]

            elif name == "list_country_codes":
                countries = []
                for c in pycountry.countries:
                    entry = {"name": c.name, "alpha_2": c.alpha_2, "alpha_3": c.alpha_3, "numeric": c.numeric}
                    if hasattr(c, "official_name") and c.official_name:
                        entry["official_name"] = c.official_name
                    countries.append(entry)
                return [TextContent(type="text", text=json.dumps({"count": len(countries), "countries": countries}))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = CountryServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
