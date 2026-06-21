import json
import random

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


BIN_DATA = {
    "4":      {"type": "Visa",       "lengths": [13, 16, 19], "format": [4, 4, 4, 4]},
    "51":     {"type": "MasterCard", "lengths": [16],          "format": [4, 4, 4, 4]},
    "52":     {"type": "MasterCard", "lengths": [16],          "format": [4, 4, 4, 4]},
    "53":     {"type": "MasterCard", "lengths": [16],          "format": [4, 4, 4, 4]},
    "54":     {"type": "MasterCard", "lengths": [16],          "format": [4, 4, 4, 4]},
    "55":     {"type": "MasterCard", "lengths": [16],          "format": [4, 4, 4, 4]},
    "2221":   {"type": "MasterCard", "lengths": [16],          "format": [4, 4, 4, 4]},
    "34":     {"type": "Amex",       "lengths": [15],          "format": [4, 6, 5]},
    "37":     {"type": "Amex",       "lengths": [15],          "format": [4, 6, 5]},
    "6011":   {"type": "Discover",   "lengths": [16, 19],      "format": [4, 4, 4, 4]},
    "65":     {"type": "Discover",   "lengths": [16, 19],      "format": [4, 4, 4, 4]},
    "300":    {"type": "Diners",     "lengths": [14, 16, 19],  "format": [4, 6, 4]},
    "301":    {"type": "Diners",     "lengths": [14, 16, 19],  "format": [4, 6, 4]},
    "302":    {"type": "Diners",     "lengths": [14, 16, 19],  "format": [4, 6, 4]},
    "303":    {"type": "Diners",     "lengths": [14, 16, 19],  "format": [4, 6, 4]},
    "304":    {"type": "Diners",     "lengths": [14, 16, 19],  "format": [4, 6, 4]},
    "305":    {"type": "Diners",     "lengths": [14, 16, 19],  "format": [4, 6, 4]},
    "36":     {"type": "Diners",     "lengths": [14, 16, 19],  "format": [4, 6, 4]},
    "38":     {"type": "Diners",     "lengths": [14, 16, 19],  "format": [4, 6, 4]},
    "3528":   {"type": "JCB",        "lengths": [16, 19],      "format": [4, 4, 4, 4]},
    "3529":   {"type": "JCB",        "lengths": [16, 19],      "format": [4, 4, 4, 4]},
    "353":    {"type": "JCB",        "lengths": [16, 19],      "format": [4, 4, 4, 4]},
    "354":    {"type": "JCB",        "lengths": [16, 19],      "format": [4, 4, 4, 4]},
    "355":    {"type": "JCB",        "lengths": [16, 19],      "format": [4, 4, 4, 4]},
    "356":    {"type": "JCB",        "lengths": [16, 19],      "format": [4, 4, 4, 4]},
    "357":    {"type": "JCB",        "lengths": [16, 19],      "format": [4, 4, 4, 4]},
    "358":    {"type": "JCB",        "lengths": [16, 19],      "format": [4, 4, 4, 4]},
}

CARD_TYPES = {
    "visa":       {"prefixes": ["4"],                              "length": 16, "format": [4, 4, 4, 4]},
    "mastercard": {"prefixes": ["51", "52", "53", "54", "55"],     "length": 16, "format": [4, 4, 4, 4]},
    "amex":       {"prefixes": ["34", "37"],                       "length": 15, "format": [4, 6, 5]},
    "discover":   {"prefixes": ["6011", "65"],                     "length": 16, "format": [4, 4, 4, 4]},
    "diners":     {"prefixes": ["300", "301", "302", "303", "304", "305", "36", "38"], "length": 14, "format": [4, 6, 4]},
    "jcb":        {"prefixes": ["3528", "3529", "353", "354", "355", "356", "357", "358"], "length": 16, "format": [4, 4, 4, 4]},
}


class CreditCardServer(Server):
    def __init__(self):
        super().__init__("credit-card")

    @staticmethod
    def _luhn_check(number: str) -> bool:
        digits = [int(d) for d in number if d.isdigit()]
        if not digits:
            return False
        total = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0

    @staticmethod
    def _detect_type(number: str) -> str:
        cleaned = "".join(d for d in number if d.isdigit())
        for prefix_len in [4, 3, 2, 1]:
            prefix = cleaned[:prefix_len]
            if prefix in BIN_DATA:
                return BIN_DATA[prefix]["type"]
        return "Unknown"

    @staticmethod
    def _generate_valid(card_type: str) -> str:
        ct = card_type.lower()
        if ct not in CARD_TYPES:
            raise ValueError(f"Unsupported card type: {card_type}. Supported: {', '.join(CARD_TYPES.keys())}")
        info = CARD_TYPES[ct]
        prefix = random.choice(info["prefixes"])
        length = info["length"]
        remaining = length - len(prefix) - 1
        number = prefix + "".join(str(random.randint(0, 9)) for _ in range(remaining))
        digits = [int(d) for d in number]
        total = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        check = (10 - total % 10) % 10
        return number + str(check)

    @staticmethod
    def _mask_number(number: str, mask_char: str = "*") -> str:
        cleaned = "".join(d for d in number if d.isdigit())
        if len(cleaned) < 8:
            return cleaned
        return cleaned[:4] + mask_char * (len(cleaned) - 8) + cleaned[-4:]

    @staticmethod
    def _format_card(number: str, separator: str = " ") -> str:
        cleaned = "".join(d for d in number if d.isdigit())
        for prefix_len in [4, 3, 2, 1]:
            prefix = cleaned[:prefix_len]
            if prefix in BIN_DATA:
                fmt = BIN_DATA[prefix]["format"]
                break
        else:
            fmt = [4, 4, 4, 4]
        parts = []
        pos = 0
        for group in fmt:
            parts.append(cleaned[pos:pos+group])
            pos += group
        return separator.join(parts)

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="validate_card", description="Validate a credit card number using Luhn algorithm", inputSchema={"type":"object","properties":{"number":{"type":"string","description":"Credit card number"}},"required":["number"]}),
            Tool(name="detect_type", description="Detect card type from number (Visa/MC/Amex/Discover/Diners/JCB)", inputSchema={"type":"object","properties":{"number":{"type":"string","description":"Credit card number"}},"required":["number"]}),
            Tool(name="bin_lookup", description="Lookup BIN information for card prefix", inputSchema={"type":"object","properties":{"bin":{"type":"string","description":"BIN prefix (first 1-6 digits)"}},"required":["bin"]}),
            Tool(name="mask_number", description="Mask middle digits of card number", inputSchema={"type":"object","properties":{"number":{"type":"string","description":"Credit card number"},"mask_char":{"type":"string","description":"Mask character","default":"*"}},"required":["number"]}),
            Tool(name="format_card", description="Format card number with separator", inputSchema={"type":"object","properties":{"number":{"type":"string","description":"Credit card number"},"separator":{"type":"string","description":"Separator character","default":" "}},"required":["number"]}),
            Tool(name="generate_valid", description="Generate a valid test card number for a given type", inputSchema={"type":"object","properties":{"card_type":{"type":"string","description":"Card type: visa, mastercard, amex, discover, diners, jcb"}},"required":["card_type"]}),
            Tool(name="luhn_check", description="Raw Luhn algorithm check on a digit string", inputSchema={"type":"object","properties":{"number":{"type":"string","description":"Number to check (digits only)"}},"required":["number"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "validate_card":
            number = args.get("number", "")
            valid = self._luhn_check(number)
            card_type = self._detect_type(number) if valid else "Unknown"
            return [TextContent(type="text", text=json.dumps({"valid": valid, "type": card_type, "number": number}))]

        if name == "detect_type":
            number = args.get("number", "")
            card_type = self._detect_type(number)
            return [TextContent(type="text", text=json.dumps({"type": card_type}))]

        if name == "bin_lookup":
            bin_prefix = args.get("bin", "")
            for prefix_len in [4, 3, 2, 1]:
                prefix = bin_prefix[:prefix_len]
                if prefix in BIN_DATA:
                    return [TextContent(type="text", text=json.dumps(BIN_DATA[prefix]))]
            return [TextContent(type="text", text=json.dumps({"type": "Unknown", "lengths": [], "format": [4, 4, 4, 4]}))]

        if name == "mask_number":
            number = args.get("number", "")
            mask_char = args.get("mask_char", "*")
            result = self._mask_number(number, mask_char)
            return [TextContent(type="text", text=json.dumps({"masked": result}))]

        if name == "format_card":
            number = args.get("number", "")
            separator = args.get("separator", " ")
            result = self._format_card(number, separator)
            return [TextContent(type="text", text=json.dumps({"formatted": result}))]

        if name == "generate_valid":
            card_type = args.get("card_type", "")
            result = self._generate_valid(card_type)
            ct = self._detect_type(result)
            return [TextContent(type="text", text=json.dumps({"number": result, "type": ct}))]

        if name == "luhn_check":
            number = args.get("number", "")
            result = self._luhn_check(number)
            return [TextContent(type="text", text=json.dumps({"valid": result}))]

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = CreditCardServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
