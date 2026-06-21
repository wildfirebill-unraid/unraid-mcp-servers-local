import json
import re

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


COUNTRY_FORMATS = {
    "US": {
        "name": "United States",
        "regex": r"^\d{5}(?:[-\s]\d{4})?$",
        "example": "90210",
        "description": "5-digit ZIP or ZIP+4 (e.g. 90210 or 90210-1234)",
        "canonical_repl": (r"^(\d{5})[-\s]?(\d{4})?$", r"\1-\2") if False else None,
    },
    "UK": {
        "name": "United Kingdom",
        "regex": r"^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$",
        "example": "SW1A 1AA",
        "description": "UK postcode format: area district sector unit (e.g. SW1A 1AA)",
    },
    "CA": {
        "name": "Canada",
        "regex": r"^[A-Z]\d[A-Z]\s?\d[A-Z]\d$",
        "example": "K1A 0B1",
        "description": "Canadian postal code: A#A #A# (e.g. K1A 0B1)",
    },
    "DE": {
        "name": "Germany",
        "regex": r"^\d{5}$",
        "example": "10115",
        "description": "German 5-digit PLZ (e.g. 10115)",
    },
    "FR": {
        "name": "France",
        "regex": r"^\d{5}$",
        "example": "75001",
        "description": "French 5-digit code postal (e.g. 75001)",
    },
    "AU": {
        "name": "Australia",
        "regex": r"^\d{4}$",
        "example": "2000",
        "description": "Australian 4-digit postcode (e.g. 2000)",
    },
}


class PostcodeServer(Server):
    def __init__(self):
        super().__init__("postcode")

    @staticmethod
    def _validate(code: str, country: str) -> bool:
        country = country.upper()
        fmt = COUNTRY_FORMATS.get(country)
        if not fmt:
            raise ValueError(f"Unsupported country: {country}")
        return bool(re.match(fmt["regex"], code.strip().upper()))

    @staticmethod
    def _format(code: str, country: str) -> str:
        country = country.upper()
        cleaned = code.strip().upper()
        if country == "US":
            m = re.match(r"^(\d{5})[-\s]?(\d{4})?$", cleaned)
            if m:
                return f"{m.group(1)}-{m.group(2)}" if m.group(2) else m.group(1)
        if country == "UK":
            cleaned = re.sub(r"\s+", "", cleaned)
            if len(cleaned) == 5:
                return f"{cleaned[:2]} {cleaned[2:]}"
            if len(cleaned) == 6:
                return f"{cleaned[:3]} {cleaned[3:]}"
            if len(cleaned) == 7:
                return f"{cleaned[:4]} {cleaned[4:]}"
            return cleaned
        if country == "CA":
            cleaned = re.sub(r"\s+", "", cleaned)
            return f"{cleaned[:3]} {cleaned[3:]}"
        return cleaned

    @staticmethod
    def _info(code: str, country: str) -> dict:
        country = country.upper()
        fmt = COUNTRY_FORMATS.get(country)
        if not fmt:
            raise ValueError(f"Unsupported country: {country}")
        valid = bool(re.match(fmt["regex"], code.strip().upper()))
        return {
            "valid": valid,
            "country": country,
            "country_name": fmt["name"],
            "code": code.strip().upper(),
            "format": fmt["description"],
            "example": fmt["example"],
        }

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="validate_postcode", description="Validate a postcode against a country's format", inputSchema={"type":"object","properties":{"code":{"type":"string","description":"Postcode to validate"},"country":{"type":"string","description":"Country code (US/UK/CA/DE/FR/AU)"}},"required":["code","country"]}),
            Tool(name="format_postcode", description="Format a postcode to canonical form", inputSchema={"type":"object","properties":{"code":{"type":"string","description":"Postcode to format"},"country":{"type":"string","description":"Country code (US/UK/CA/DE/FR/AU)"}},"required":["code","country"]}),
            Tool(name="postcode_info", description="Get detailed info about a postcode", inputSchema={"type":"object","properties":{"code":{"type":"string","description":"Postcode to look up"},"country":{"type":"string","description":"Country code (US/UK/CA/DE/FR/AU)"}},"required":["code","country"]}),
            Tool(name="list_countries", description="List supported countries with their postcode formats", inputSchema={"type":"object","properties":{}}),
            Tool(name="suggest_format", description="Show expected postcode format for a country", inputSchema={"type":"object","properties":{"country":{"type":"string","description":"Country code (US/UK/CA/DE/FR/AU)"}},"required":["country"]}),
            Tool(name="bulk_validate", description="Validate multiple postcode/country pairs", inputSchema={"type":"object","properties":{"codes":{"type":"array","items":{"type":"object","properties":{"code":{"type":"string","description":"Postcode"},"country":{"type":"string","description":"Country code"}},"required":["code","country"]},"description":"Array of postcode/country objects"}},"required":["codes"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "validate_postcode":
            code = args.get("code", "")
            country = args.get("country", "")
            result = self._validate(code, country)
            return [TextContent(type="text", text=json.dumps({"valid": result, "code": code, "country": country.upper()}))]

        if name == "format_postcode":
            code = args.get("code", "")
            country = args.get("country", "")
            result = self._format(code, country)
            return [TextContent(type="text", text=json.dumps({"formatted": result, "original": code, "country": country.upper()}))]

        if name == "postcode_info":
            code = args.get("code", "")
            country = args.get("country", "")
            result = self._info(code, country)
            return [TextContent(type="text", text=json.dumps(result))]

        if name == "list_countries":
            result = {}
            for cc, fmt in COUNTRY_FORMATS.items():
                result[cc] = {"name": fmt["name"], "format": fmt["description"], "example": fmt["example"]}
            return [TextContent(type="text", text=json.dumps({"countries": result}))]

        if name == "suggest_format":
            country = args.get("country", "").upper()
            fmt = COUNTRY_FORMATS.get(country)
            if not fmt:
                raise ValueError(f"Unsupported country: {country}")
            return [TextContent(type="text", text=json.dumps({"country": country, "country_name": fmt["name"], "format": fmt["description"], "example": fmt["example"], "regex": fmt["regex"]}))]

        if name == "bulk_validate":
            codes = args.get("codes", [])
            results = []
            for item in codes:
                code = item.get("code", "")
                country = item.get("country", "")
                try:
                    valid = self._validate(code, country)
                    results.append({"code": code, "country": country.upper(), "valid": valid, "error": None})
                except ValueError as e:
                    results.append({"code": code, "country": country.upper(), "valid": False, "error": str(e)})
            return [TextContent(type="text", text=json.dumps({"results": results}))]

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = PostcodeServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
