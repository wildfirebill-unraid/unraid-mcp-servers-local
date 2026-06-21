import json
import re

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

class BytesizeServer(Server):
    def __init__(self):
        super().__init__("bytesize")

    SI_UNITS = {"B":1,"KB":3,"MB":6,"GB":9,"TB":12,"PB":15,"EB":18}
    BINARY_UNITS = {"B":1,"KiB":10,"MiB":20,"GiB":30,"TiB":40,"PiB":50,"EiB":60}

    @staticmethod
    def _parse_to_bytes(size_str: str) -> int:
        size_str = size_str.strip()
        m = re.match(r'^([\d.]+)\s*(B|KB|MB|GB|TB|PB|EB|KiB|MiB|GiB|TiB|PiB|EiB|K|M|G|T|P|E)$', size_str, re.IGNORECASE)
        if not m:
            raise ValueError(f"Cannot parse size: {size_str}")
        val = float(m.group(1))
        unit = m.group(2).upper()
        alias = {"K":"KB","M":"MB","G":"GB","T":"TB","P":"PB","E":"EB"}
        unit = alias.get(unit, unit)
        if unit in BytesizeServer.BINARY_UNITS:
            shift = BytesizeServer.BINARY_UNITS[unit]
            return int(val * (1024 ** (shift // 10)))
        elif unit in BytesizeServer.SI_UNITS:
            exp = BytesizeServer.SI_UNITS[unit] // 3
            return int(val * (1000 ** exp))
        raise ValueError(f"Unknown unit: {unit}")

    @staticmethod
    def _format_si(b: int) -> str:
        if b < 1000:
            return f"{b} B"
        for unit in ["KB","MB","GB","TB","PB","EB"]:
            if b < 1000:
                return f"{b:.2f} {unit}"
            b /= 1000
        return f"{b:.2f} EB"

    @staticmethod
    def _format_binary(b: int) -> str:
        if b < 1024:
            return f"{b} B"
        for unit in ["KiB","MiB","GiB","TiB","PiB","EiB"]:
            if b < 1024:
                return f"{b:.2f} {unit}"
            b /= 1024
        return f"{b:.2f} EiB"

    @staticmethod
    def _format_bytes(b: int, style: str) -> str:
        if style == "si":
            return BytesizeServer._format_si(b)
        elif style == "binary":
            return BytesizeServer._format_binary(b)
        elif style == "hybrid":
            si = BytesizeServer._format_si(b)
            bi = BytesizeServer._format_binary(b)
            return f"{si} ({bi})"
        else:
            raise ValueError(f"Unknown style: {style}")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="format_bytes", description="Convert bytes to human-readable string",
                 inputSchema={"type":"object","properties":{"bytes":{"type":"integer","description":"Number of bytes"},"style":{"type":"string","description":"Formatting style: si, binary, or hybrid","default":"si","enum":["si","binary","hybrid"]}},"required":["bytes"]}),
            Tool(name="parse_size", description="Parse a human-readable size string to bytes",
                 inputSchema={"type":"object","properties":{"size_str":{"type":"string","description":"Size string like '1.5 GB' or '500 MiB'"}},"required":["size_str"]}),
            Tool(name="convert_unit", description="Convert a size between units",
                 inputSchema={"type":"object","properties":{"bytes":{"type":"integer","description":"Number of bytes"},"from_unit":{"type":"string","description":"Source unit (B, KB, MB, GB, TB, KiB, MiB, GiB, TiB)"},"to_unit":{"type":"string","description":"Target unit (B, KB, MB, GB, TB, KiB, MiB, GiB, TiB)"}},"required":["bytes","from_unit","to_unit"]}),
            Tool(name="size_comparison", description="Compare multiple size strings and return sorted order",
                 inputSchema={"type":"object","properties":{"sizes":{"type":"array","items":{"type":"string"},"description":"List of size strings to compare"}},"required":["sizes"]}),
            Tool(name="batch_format", description="Format multiple byte values at once",
                 inputSchema={"type":"object","properties":{"sizes":{"type":"array","items":{"type":"integer"},"description":"List of byte values"},"style":{"type":"string","description":"Formatting style: si, binary, or hybrid","default":"si","enum":["si","binary","hybrid"]}},"required":["sizes"]}),
            Tool(name="list_units", description="List available units for a system",
                 inputSchema={"type":"object","properties":{"system":{"type":"string","description":"Unit system: si, binary, or all","default":"all","enum":["si","binary","all"]}},"required":[]}),
            Tool(name="size_info", description="Parse a size string and show its value in all units",
                 inputSchema={"type":"object","properties":{"size_str":{"type":"string","description":"Size string to analyze"}},"required":["size_str"]}),
            Tool(name="add_sizes", description="Add multiple size strings together",
                 inputSchema={"type":"object","properties":{"sizes":{"type":"array","items":{"type":"string"},"description":"List of size strings to sum"}},"required":["sizes"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        try:
            args = arguments or {}
            if name == "format_bytes":
                b = int(args["bytes"])
                style = args.get("style", "si")
                result = self._format_bytes(b, style)
                return [TextContent(type="text", text=json.dumps({"formatted": result}, indent=2))]

            if name == "parse_size":
                parsed = self._parse_to_bytes(args["size_str"])
                return [TextContent(type="text", text=json.dumps({"bytes": parsed}, indent=2))]

            if name == "convert_unit":
                b = int(args["bytes"])
                from_unit = args["from_unit"].upper()
                to_unit = args["to_unit"].upper()
                alias = {"K":"KB","M":"MB","G":"GB","T":"TB","P":"PB","E":"EB"}
                from_unit = alias.get(from_unit, from_unit)
                to_unit = alias.get(to_unit, to_unit)
                system = si if from_unit in self.SI_UNITS and to_unit in self.SI_UNITS else binary
                if from_unit in self.SI_UNITS and to_unit in self.SI_UNITS:
                    return [TextContent(type="text", text=json.dumps({"value": b / 1000 ** (self.SI_UNITS[from_unit]//3) * 1000 ** (self.SI_UNITS[to_unit]//3)}, indent=2))]
                elif from_unit in self.BINARY_UNITS and to_unit in self.BINARY_UNITS:
                    return [TextContent(type="text", text=json.dumps({"value": b / 1024 ** (self.BINARY_UNITS[from_unit]//10) * 1024 ** (self.BINARY_UNITS[to_unit]//10)}, indent=2))]
                else:
                    bytes_val = self._parse_to_bytes(f"{b} {from_unit}")
                    if to_unit in self.SI_UNITS:
                        exp = self.SI_UNITS[to_unit] // 3
                        conv = bytes_val / (1000 ** exp)
                    else:
                        shift = self.BINARY_UNITS[to_unit] // 10
                        conv = bytes_val / (1024 ** shift)
                    return [TextContent(type="text", text=json.dumps({"value": conv}, indent=2))]

            if name == "size_comparison":
                sizes = []
                for s in args["sizes"]:
                    sizes.append((s, self._parse_to_bytes(s)))
                sizes.sort(key=lambda x: x[1])
                return [TextContent(type="text", text=json.dumps({
                    "sorted": [s[0] for s in sizes],
                    "largest": sizes[-1][0],
                    "smallest": sizes[0][0],
                }, indent=2))]

            if name == "batch_format":
                style = args.get("style", "si")
                results = [self._format_bytes(b, style) for b in args["sizes"]]
                return [TextContent(type="text", text=json.dumps({"formatted": results}, indent=2))]

            if name == "list_units":
                system = args.get("system", "all")
                if system == "si":
                    units = list(self.SI_UNITS.keys())
                elif system == "binary":
                    units = list(self.BINARY_UNITS.keys())
                else:
                    units = {"si": list(self.SI_UNITS.keys()), "binary": list(self.BINARY_UNITS.keys())}
                return [TextContent(type="text", text=json.dumps({"units": units}, indent=2))]

            if name == "size_info":
                b = self._parse_to_bytes(args["size_str"])
                info = {"bytes": b}
                for unit, exp in self.SI_UNITS.items():
                    info[unit] = b / (1000 ** (exp // 3))
                for unit, shift in self.BINARY_UNITS.items():
                    info[unit] = b / (1024 ** (shift // 10))
                return [TextContent(type="text", text=json.dumps(info, indent=2))]

            if name == "add_sizes":
                total = sum(self._parse_to_bytes(s) for s in args["sizes"])
                return [TextContent(type="text", text=json.dumps({
                    "total_bytes": total,
                    "formatted_si": self._format_si(total),
                    "formatted_binary": self._format_binary(total),
                }, indent=2))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    server = BytesizeServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
