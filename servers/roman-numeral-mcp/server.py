import json
import re

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

class RomanNumeralServer(Server):
    def __init__(self):
        super().__init__("roman-numeral")

    ROMAN_MAP = [
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    ]
    ROMAN_RE = re.compile(r'^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$', re.IGNORECASE)

    @staticmethod
    def _to_roman(n: int) -> str:
        if not 1 <= n <= 3999:
            raise ValueError("Number must be between 1 and 3999")
        result = []
        for value, numeral in RomanNumeralServer.ROMAN_MAP:
            while n >= value:
                result.append(numeral)
                n -= value
        return "".join(result)

    @staticmethod
    def _from_roman(s: str) -> int:
        s = s.strip().upper()
        if not RomanNumeralServer.ROMAN_RE.match(s):
            raise ValueError(f"Invalid Roman numeral: {s}")
        result = 0
        i = 0
        for value, numeral in RomanNumeralServer.ROMAN_MAP:
            while s[i:i+len(numeral)] == numeral:
                result += value
                i += len(numeral)
        if i != len(s):
            raise ValueError(f"Invalid Roman numeral: {s}")
        return result

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="to_roman", description="Convert an integer to Roman numeral",
                 inputSchema={"type":"object","properties":{"integer":{"type":"integer","description":"Integer between 1 and 3999"}},"required":["integer"]}),
            Tool(name="from_roman", description="Convert a Roman numeral to integer",
                 inputSchema={"type":"object","properties":{"roman":{"type":"string","description":"Roman numeral string (e.g. XIV)"}},"required":["roman"]}),
            Tool(name="roman_add", description="Add two Roman numerals and return the sum as Roman",
                 inputSchema={"type":"object","properties":{"roman1":{"type":"string","description":"First Roman numeral"},"roman2":{"type":"string","description":"Second Roman numeral"}},"required":["roman1","roman2"]}),
            Tool(name="roman_validate", description="Check if a string is a valid Roman numeral",
                 inputSchema={"type":"object","properties":{"roman":{"type":"string","description":"String to validate"}},"required":["roman"]}),
            Tool(name="roman_range", description="List Roman numerals in a range",
                 inputSchema={"type":"object","properties":{"start":{"type":"integer","description":"Start integer (1-3999)"},"end":{"type":"integer","description":"End integer (1-3999)"}},"required":["start","end"]}),
            Tool(name="roman_stats", description="Analyze Roman numerals found in text",
                 inputSchema={"type":"object","properties":{"text":{"type":"string","description":"Text to scan for Roman numerals"}},"required":["text"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        try:
            args = arguments or {}
            if name == "to_roman":
                n = int(args["integer"])
                result = self._to_roman(n)
                return [TextContent(type="text", text=json.dumps({"roman": result}, indent=2))]

            if name == "from_roman":
                result = self._from_roman(args["roman"])
                return [TextContent(type="text", text=json.dumps({"integer": result}, indent=2))]

            if name == "roman_add":
                a = self._from_roman(args["roman1"])
                b = self._from_roman(args["roman2"])
                total = a + b
                if total > 3999:
                    raise ValueError(f"Sum {total} exceeds 3999, cannot represent as Roman numeral")
                result = self._to_roman(total)
                return [TextContent(type="text", text=json.dumps({
                    "a": args["roman1"],
                    "b": args["roman2"],
                    "a_value": a,
                    "b_value": b,
                    "sum": total,
                    "roman": result,
                }, indent=2))]

            if name == "roman_validate":
                s = args["roman"].strip().upper()
                valid = bool(self.ROMAN_RE.match(s)) and 1 <= self._from_roman(s) <= 3999
                return [TextContent(type="text", text=json.dumps({
                    "valid": valid,
                    "roman": args["roman"],
                }, indent=2))]

            if name == "roman_range":
                start = int(args["start"])
                end = int(args["end"])
                if not 1 <= start <= end <= 3999:
                    raise ValueError("Range must be 1-3999 and start <= end")
                result = [self._to_roman(n) for n in range(start, end + 1)]
                return [TextContent(type="text", text=json.dumps({
                    "start": start,
                    "end": end,
                    "count": len(result),
                    "numerals": result,
                }, indent=2))]

            if name == "roman_stats":
                text = args["text"]
                candidates = re.findall(r'\b[IVXLCDM]+\b', text.upper())
                valid_romans = []
                for c in set(candidates):
                    try:
                        v = self._from_roman(c)
                        if 1 <= v <= 3999:
                            valid_romans.append({"roman": c, "value": v})
                    except ValueError:
                        pass
                valid_romans.sort(key=lambda x: x["value"])
                return [TextContent(type="text", text=json.dumps({
                    "found_count": len(valid_romans),
                    "numerals": valid_romans,
                }, indent=2))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    server = RomanNumeralServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
