import json
import locale as locale_mod
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

import pycountry


_CURRENCY_MINOR_UNITS = {
    "AED": 2, "AFN": 2, "ALL": 2, "AMD": 2, "ANG": 2, "AOA": 2, "ARS": 2,
    "AUD": 2, "AWG": 2, "AZN": 2, "BAM": 2, "BBD": 2, "BDT": 2, "BGN": 2,
    "BHD": 3, "BIF": 0, "BMD": 2, "BND": 2, "BOB": 2, "BOV": 2, "BRL": 2,
    "BSD": 2, "BTN": 2, "BWP": 2, "BYN": 2, "BZD": 2, "CAD": 2, "CDF": 2,
    "CHE": 2, "CHF": 2, "CHW": 2, "CLF": 4, "CLP": 0, "CNY": 2, "COP": 2,
    "COU": 2, "CRC": 2, "CUC": 2, "CUP": 2, "CVE": 2, "CZK": 2, "DJF": 0,
    "DKK": 2, "DOP": 2, "DZD": 2, "EGP": 2, "ERN": 2, "ETB": 2, "EUR": 2,
    "FJD": 2, "FKP": 2, "GBP": 2, "GEL": 2, "GHS": 2, "GIP": 2, "GMD": 2,
    "GNF": 0, "GTQ": 2, "GYD": 2, "HKD": 2, "HNL": 2, "HRK": 2, "HTG": 2,
    "HUF": 2, "IDR": 2, "ILS": 2, "INR": 2, "IQD": 3, "IRR": 2, "ISK": 0,
    "JMD": 2, "JOD": 3, "JPY": 0, "KES": 2, "KGS": 2, "KHR": 2, "KMF": 0,
    "KPW": 2, "KRW": 0, "KWD": 3, "KYD": 2, "KZT": 2, "LAK": 2, "LBP": 2,
    "LKR": 2, "LRD": 2, "LSL": 2, "LYD": 3, "MAD": 2, "MDL": 2, "MGA": 2,
    "MKD": 2, "MMK": 2, "MNT": 2, "MOP": 2, "MRU": 2, "MUR": 2, "MVR": 2,
    "MWK": 2, "MXN": 2, "MXV": 2, "MYR": 2, "MZN": 2, "NAD": 2, "NGN": 2,
    "NIO": 2, "NOK": 2, "NPR": 2, "NZD": 2, "OMR": 3, "PAB": 2, "PEN": 2,
    "PGK": 2, "PHP": 2, "PKR": 2, "PLN": 2, "PYG": 0, "QAR": 2, "RON": 2,
    "RSD": 2, "RUB": 2, "RWF": 0, "SAR": 2, "SBD": 2, "SCR": 2, "SDG": 2,
    "SEK": 2, "SGD": 2, "SHP": 2, "SLE": 2, "SLL": 2, "SOS": 2, "SRD": 2,
    "SSP": 2, "STN": 2, "SVC": 2, "SYP": 2, "SZL": 2, "THB": 2, "TJS": 2,
    "TMT": 2, "TND": 3, "TOP": 2, "TRY": 2, "TTD": 2, "TWD": 2, "TZS": 2,
    "UAH": 2, "UGX": 0, "USD": 2, "USN": 2, "UYI": 0, "UYU": 2, "UYW": 4,
    "UZS": 2, "VED": 2, "VES": 2, "VND": 0, "VUV": 0, "WST": 2, "XAF": 0,
    "XAG": 0, "XAU": 0, "XBA": 0, "XBB": 0, "XBC": 0, "XBD": 0, "XCD": 2,
    "XDR": 0, "XOF": 0, "XPD": 0, "XPF": 0, "XPT": 0, "XSU": 0, "XTS": 0,
    "XUA": 0, "XXX": 0, "YER": 2, "ZAR": 2, "ZMW": 2, "ZWG": 2,
}


def _currency_to_dict(c: Any) -> dict:
    return {
        "code": c.alpha_3,
        "name": c.name,
        "numeric": getattr(c, "numeric", None),
    }


class CurrencyServer(Server):
    def __init__(self):
        super().__init__("currency")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="currency_info",
                description="Get currency information by alphabetic code",
                inputSchema={
                    "type": "object",
                    "properties": {"code": {"type": "string", "description": "Currency alphabetic code (e.g. USD, EUR)"}},
                    "required": ["code"],
                },
            ),
            Tool(
                name="search_currency",
                description="Search for currencies by name",
                inputSchema={
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Currency name or partial name to search"}},
                    "required": ["query"],
                },
            ),
            Tool(
                name="list_currencies",
                description="List all currencies",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="country_currencies",
                description="List currencies used in a specific country",
                inputSchema={
                    "type": "object",
                    "properties": {"country_code": {"type": "string", "description": "Alpha-2 country code"}},
                    "required": ["country_code"],
                },
            ),
            Tool(
                name="convert_numeric",
                description="Convert a numeric currency code to alphabetic code",
                inputSchema={
                    "type": "object",
                    "properties": {"numeric_code": {"type": "string", "description": "Numeric currency code (e.g. '840' for USD)"}},
                    "required": ["numeric_code"],
                },
            ),
            Tool(
                name="format_amount",
                description="Format a currency amount for display",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Amount to format"},
                        "currency_code": {"type": "string", "description": "Currency alphabetic code"},
                        "locale": {"type": "string", "description": "Locale string (e.g. 'en_US', 'de_DE')"},
                    },
                    "required": ["amount", "currency_code"],
                },
            ),
            Tool(
                name="list_minor_units",
                description="List all currencies with their minor unit (decimal) precision",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}

        try:
            if name == "currency_info":
                code = args.get("code", "").upper().strip()
                currency = pycountry.currencies.get(alpha_3=code)
                if not currency:
                    return [TextContent(type="text", text=json.dumps({"error": f"Currency not found: {code}"}))]
                result = _currency_to_dict(currency)
                result["minor_unit"] = _CURRENCY_MINOR_UNITS.get(code, 2)
                return [TextContent(type="text", text=json.dumps(result))]

            elif name == "search_currency":
                query = args.get("query", "").lower()
                results = []
                for c in pycountry.currencies:
                    if query in c.name.lower():
                        entry = _currency_to_dict(c)
                        entry["minor_unit"] = _CURRENCY_MINOR_UNITS.get(c.alpha_3, 2)
                        results.append(entry)
                return [TextContent(type="text", text=json.dumps({"query": query, "count": len(results), "results": results}))]

            elif name == "list_currencies":
                currencies = []
                for c in pycountry.currencies:
                    entry = _currency_to_dict(c)
                    entry["minor_unit"] = _CURRENCY_MINOR_UNITS.get(c.alpha_3, 2)
                    currencies.append(entry)
                return [TextContent(type="text", text=json.dumps({"count": len(currencies), "currencies": currencies}))]

            elif name == "country_currencies":
                country_code = args.get("country_code", "").upper().strip()
                country = pycountry.countries.get(alpha_2=country_code)
                if not country:
                    return [TextContent(type="text", text=json.dumps({"error": f"Country not found: {country_code}"}))]
                currencies = []
                for c in pycountry.currencies:
                    currencies.append(_currency_to_dict(c))
                result = {
                    "country": country.name,
                    "country_code": country_code,
                    "currencies": currencies,
                }
                return [TextContent(type="text", text=json.dumps(result))]

            elif name == "convert_numeric":
                numeric_code = args.get("numeric_code", "").strip()
                if not numeric_code.isdigit():
                    return [TextContent(type="text", text=json.dumps({"error": "Numeric code must be digits"}))]
                currency = pycountry.currencies.get(numeric=numeric_code)
                if not currency:
                    return [TextContent(type="text", text=json.dumps({"error": f"No currency found with numeric code: {numeric_code}"}))]
                return [TextContent(type="text", text=json.dumps({
                    "numeric": numeric_code,
                    "alphabetic": currency.alpha_3,
                    "name": currency.name,
                }))]

            elif name == "format_amount":
                amount = args.get("amount", 0)
                currency_code = args.get("currency_code", "").upper().strip()
                loc = args.get("locale", "en_US")

                currency = pycountry.currencies.get(alpha_3=currency_code)
                if not currency:
                    return [TextContent(type="text", text=json.dumps({"error": f"Currency not found: {currency_code}"}))]

                formatted = f"{currency_code} {amount:,.{_CURRENCY_MINOR_UNITS.get(currency_code, 2)}f}"
                try:
                    locale_mod.setlocale(locale_mod.LC_ALL, loc)
                    formatted = locale_mod.currency(amount, symbol=True, grouping=True)
                except (locale_mod.Error, ValueError):
                    formatted = f"{currency_code} {amount:,.{_CURRENCY_MINOR_UNITS.get(currency_code, 2)}f}"

                return [TextContent(type="text", text=json.dumps({
                    "amount": amount,
                    "currency": currency_code,
                    "locale": loc,
                    "formatted": formatted,
                }))]

            elif name == "list_minor_units":
                currencies = []
                for c in pycountry.currencies:
                    currencies.append({
                        "code": c.alpha_3,
                        "name": c.name,
                        "minor_unit": _CURRENCY_MINOR_UNITS.get(c.alpha_3, 2),
                    })
                return [TextContent(type="text", text=json.dumps({"count": len(currencies), "currencies": currencies}))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = CurrencyServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
