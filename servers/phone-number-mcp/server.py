import json
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

import phonenumbers
from phonenumbers import carrier, geocoder, timezone as pn_timezone
from phonenumbers import PhoneNumberType, PhoneNumberFormat


_TYPE_NAMES = {
    PhoneNumberType.FIXED_LINE: "fixed_line",
    PhoneNumberType.MOBILE: "mobile",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed_line_or_mobile",
    PhoneNumberType.TOLL_FREE: "toll_free",
    PhoneNumberType.PREMIUM_RATE: "premium_rate",
    PhoneNumberType.SHARED_COST: "shared_cost",
    PhoneNumberType.VOIP: "voip",
    PhoneNumberType.PERSONAL_NUMBER: "personal_number",
    PhoneNumberType.PAGER: "pager",
    PhoneNumberType.UAN: "uan",
    PhoneNumberType.VOICEMAIL: "voicemail",
    PhoneNumberType.UNKNOWN: "unknown",
}

_FORMAT_MAP = {
    "international": PhoneNumberFormat.INTERNATIONAL,
    "national": PhoneNumberFormat.NATIONAL,
    "e164": PhoneNumberFormat.E164,
    "rfc3966": PhoneNumberFormat.RFC3966,
}

_TYPE_INPUT_MAP = {
    "fixed_line": PhoneNumberType.FIXED_LINE,
    "mobile": PhoneNumberType.MOBILE,
    "fixed_line_or_mobile": PhoneNumberType.FIXED_LINE_OR_MOBILE,
    "toll_free": PhoneNumberType.TOLL_FREE,
    "premium_rate": PhoneNumberType.PREMIUM_RATE,
    "shared_cost": PhoneNumberType.SHARED_COST,
    "voip": PhoneNumberType.VOIP,
    "personal_number": PhoneNumberType.PERSONAL_NUMBER,
    "pager": PhoneNumberType.PAGER,
    "uan": PhoneNumberType.UAN,
    "voicemail": PhoneNumberType.VOICEMAIL,
}


def _parse_safe(number: str, region: str | None) -> phonenumbers.PhoneNumber | None:
    try:
        if region:
            return phonenumbers.parse(number, region)
        return phonenumbers.parse(number, None)
    except phonenumbers.NumberParseException:
        return None


def _number_to_dict(num: phonenumbers.PhoneNumber) -> dict:
    return {
        "country_code": num.country_code,
        "national_number": num.national_number,
        "extension": num.extension or None,
        "italian_leading_zero": num.italian_leading_zero,
        "number_of_leading_zeros": num.number_of_leading_zeros,
        "raw_input": num.raw_input or None,
    }


class PhoneNumberServer(Server):
    def __init__(self):
        super().__init__("phone-number")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="parse",
                description="Parse a phone number into its components",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "number": {"type": "string", "description": "Phone number string to parse"},
                        "region": {"type": "string", "description": "ISO 3166-1 alpha-2 region code (e.g. 'US', 'GB'). Optional if number starts with +"},
                    },
                    "required": ["number"],
                },
            ),
            Tool(
                name="format",
                description="Format a phone number in the specified format",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "number": {"type": "string", "description": "Phone number string"},
                        "region": {"type": "string", "description": "Region code (optional if + prefix used)"},
                        "fmt": {"type": "string", "description": "Output format", "enum": ["international", "national", "e164", "rfc3966"]},
                    },
                    "required": ["number"],
                },
            ),
            Tool(
                name="validate",
                description="Validate whether a phone number is valid",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "number": {"type": "string", "description": "Phone number string"},
                        "region": {"type": "string", "description": "Region code (optional)"},
                    },
                    "required": ["number"],
                },
            ),
            Tool(
                name="info",
                description="Get full information about a phone number (type, validity, carrier, timezone, geocode)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "number": {"type": "string", "description": "Phone number string"},
                        "region": {"type": "string", "description": "Region code (optional)"},
                    },
                    "required": ["number"],
                },
            ),
            Tool(
                name="list_regions",
                description="List all supported region codes for phone number parsing",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="example",
                description="Get an example phone number for a region",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "region": {"type": "string", "description": "ISO 3166-1 alpha-2 region code"},
                        "type": {"type": "string", "description": "Number type: mobile, fixed_line, toll_free, voip, etc."},
                    },
                    "required": ["region"],
                },
            ),
            Tool(
                name="timezone",
                description="Get the timezone(s) for a phone number",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "number": {"type": "string", "description": "Phone number string"},
                        "region": {"type": "string", "description": "Region code (optional)"},
                    },
                    "required": ["number"],
                },
            ),
            Tool(
                name="is_possible",
                description="Quick check if a phone number is possible (faster than full validation)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "number": {"type": "string", "description": "Phone number string"},
                        "region": {"type": "string", "description": "Region code (optional)"},
                    },
                    "required": ["number"],
                },
            ),
            Tool(
                name="geocode",
                description="Get the geographical description for a phone number",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "number": {"type": "string", "description": "Phone number string"},
                        "region": {"type": "string", "description": "Region code (optional)"},
                    },
                    "required": ["number"],
                },
            ),
            Tool(
                name="carrier",
                description="Get the carrier name for a phone number",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "number": {"type": "string", "description": "Phone number string"},
                        "region": {"type": "string", "description": "Region code (optional)"},
                    },
                    "required": ["number"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}

        try:
            if name == "parse":
                num_str = args.get("number", "")
                region = args.get("region")
                parsed = _parse_safe(num_str, region)
                if not parsed:
                    return [TextContent(type="text", text=json.dumps({"error": f"Could not parse number: {num_str}"}))]
                result = _number_to_dict(parsed)
                region_code = phonenumbers.region_code_for_number(parsed)
                if region_code:
                    result["region"] = region_code
                return [TextContent(type="text", text=json.dumps(result))]

            elif name == "format":
                num_str = args.get("number", "")
                region = args.get("region")
                fmt_name = args.get("fmt", "international")
                fmt = _FORMAT_MAP.get(fmt_name, PhoneNumberFormat.INTERNATIONAL)
                parsed = _parse_safe(num_str, region)
                if not parsed:
                    return [TextContent(type="text", text=json.dumps({"error": f"Could not parse number: {num_str}"}))]
                formatted = phonenumbers.format_number(parsed, fmt)
                return [TextContent(type="text", text=json.dumps({"formatted": formatted, "format": fmt_name}))]

            elif name == "validate":
                num_str = args.get("number", "")
                region = args.get("region")
                parsed = _parse_safe(num_str, region)
                if not parsed:
                    return [TextContent(type="text", text=json.dumps({"valid": False, "possible": False, "error": "Could not parse number"}))]
                valid = phonenumbers.is_valid_number(parsed)
                possible = phonenumbers.is_possible_number(parsed)
                return [TextContent(type="text", text=json.dumps({"valid": valid, "possible": possible}))]

            elif name == "info":
                num_str = args.get("number", "")
                region = args.get("region")
                parsed = _parse_safe(num_str, region)
                if not parsed:
                    return [TextContent(type="text", text=json.dumps({"error": f"Could not parse number: {num_str}"}))
                    ]
                ntype = phonenumbers.number_type(parsed)
                region_code = phonenumbers.region_code_for_number(parsed) or region
                result = {
                    "parsed": _number_to_dict(parsed),
                    "valid": phonenumbers.is_valid_number(parsed),
                    "possible": phonenumbers.is_possible_number(parsed),
                    "type": _TYPE_NAMES.get(ntype, "unknown"),
                    "region": region_code or None,
                }
                try:
                    result["carrier"] = carrier.name_for_number(parsed, "en")
                except Exception:
                    pass
                try:
                    result["timezone"] = pn_timezone.time_zones_for_number(parsed)
                except Exception:
                    pass
                try:
                    result["geocode"] = geocoder.description_for_number(parsed, "en")
                except Exception:
                    pass
                return [TextContent(type="text", text=json.dumps(result))]

            elif name == "list_regions":
                regions = sorted(phonenumbers.SUPPORTED_REGIONS)
                return [TextContent(type="text", text=json.dumps({"count": len(regions), "regions": regions}))]

            elif name == "example":
                region_code = args.get("region", "").upper().strip()
                type_name = args.get("type", "mobile")
                ptype = _TYPE_INPUT_MAP.get(type_name, PhoneNumberType.MOBILE)
                if type_name and type_name != "mobile":
                    ex = phonenumbers.example_number_for_type(region_code, ptype)
                else:
                    ex = phonenumbers.example_number(region_code)
                if not ex:
                    return [TextContent(type="text", text=json.dumps({"error": f"No example number for region: {region_code}"}))]
                formatted = phonenumbers.format_number(ex, PhoneNumberFormat.INTERNATIONAL)
                return [TextContent(type="text", text=json.dumps({
                    "region": region_code,
                    "type": type_name or "mobile",
                    "number": formatted,
                    "parsed": _number_to_dict(ex),
                }))]

            elif name == "timezone":
                num_str = args.get("number", "")
                region = args.get("region")
                parsed = _parse_safe(num_str, region)
                if not parsed:
                    return [TextContent(type="text", text=json.dumps({"error": f"Could not parse number: {num_str}"}))]
                tzones = pn_timezone.time_zones_for_number(parsed)
                return [TextContent(type="text", text=json.dumps({"timezones": tzones}))]

            elif name == "is_possible":
                num_str = args.get("number", "")
                region = args.get("region")
                parsed = _parse_safe(num_str, region)
                if not parsed:
                    return [TextContent(type="text", text=json.dumps({"possible": False}))]
                possible = phonenumbers.is_possible_number(parsed)
                return [TextContent(type="text", text=json.dumps({"possible": possible}))]

            elif name == "geocode":
                num_str = args.get("number", "")
                region = args.get("region")
                parsed = _parse_safe(num_str, region)
                if not parsed:
                    return [TextContent(type="text", text=json.dumps({"error": f"Could not parse number: {num_str}"}))]
                desc = geocoder.description_for_number(parsed, "en")
                return [TextContent(type="text", text=json.dumps({"description": desc or None}))]

            elif name == "carrier":
                num_str = args.get("number", "")
                region = args.get("region")
                parsed = _parse_safe(num_str, region)
                if not parsed:
                    return [TextContent(type="text", text=json.dumps({"error": f"Could not parse number: {num_str}"}))]
                name_carrier = carrier.name_for_number(parsed, "en")
                return [TextContent(type="text", text=json.dumps({"carrier": name_carrier or None}))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = PhoneNumberServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
