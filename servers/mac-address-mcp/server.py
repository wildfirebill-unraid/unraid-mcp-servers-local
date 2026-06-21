import json
import random
import re

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

class MacAddressServer(Server):
    def __init__(self):
        super().__init__("mac-address")

    @staticmethod
    def _normalize(mac: str) -> str:
        cleaned = re.sub(r'[^0-9a-fA-F]', '', mac)
        if len(cleaned) != 12:
            raise ValueError(f"Invalid MAC address: {mac}")
        return cleaned.lower()

    @staticmethod
    def _format_mac_raw(hex_str: str, style: str) -> str:
        if style == "colon":
            return ':'.join(hex_str[i:i+2] for i in range(0, 12, 2))
        elif style == "hyphen":
            return '-'.join(hex_str[i:i+2] for i in range(0, 12, 2))
        elif style == "dot":
            return '.'.join(hex_str[i:i+4] for i in range(0, 12, 4))
        elif style == "cisco":
            return '.'.join(hex_str[i:i+4] for i in range(0, 12, 4))
        elif style == "no_separator":
            return hex_str
        else:
            raise ValueError(f"Unknown style: {style}")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="validate_mac", description="Validate if a string is a valid MAC address",
                 inputSchema={"type":"object","properties":{"mac":{"type":"string","description":"MAC address to validate"}},"required":["mac"]}),
            Tool(name="format_mac", description="Convert MAC address between formatting styles",
                 inputSchema={"type":"object","properties":{"mac":{"type":"string","description":"MAC address"},"style":{"type":"string","description":"Output style: colon, hyphen, dot, cisco, no_separator","enum":["colon","hyphen","dot","cisco","no_separator"]}},"required":["mac","style"]}),
            Tool(name="lookup_oui", description="Look up OUI vendor by MAC address (requires local vendor DB)",
                 inputSchema={"type":"object","properties":{"mac":{"type":"string","description":"MAC address to look up"}},"required":["mac"]}),
            Tool(name="generate_mac", description="Generate one or more MAC addresses, optionally with an OUI prefix",
                 inputSchema={"type":"object","properties":{"prefix":{"type":"string","description":"Optional OUI prefix (6 hex chars, e.g. 00:1A:2B)"},"count":{"type":"integer","description":"Number of MACs to generate (default 1)","default":1},"style":{"type":"string","description":"Output style: colon, hyphen, dot, cisco, no_separator","default":"colon","enum":["colon","hyphen","dot","cisco","no_separator"]}},"required":[]}),
            Tool(name="mac_info", description="Get MAC type info (unicast/multicast, universal/local)",
                 inputSchema={"type":"object","properties":{"mac":{"type":"string","description":"MAC address to analyze"}},"required":["mac"]}),
            Tool(name="vendor_search", description="Search OUI vendor database (requires local vendor DB)",
                 inputSchema={"type":"object","properties":{"query":{"type":"string","description":"Vendor name or partial OUI to search"}},"required":["query"]}),
            Tool(name="random_mac", description="Generate a random MAC address",
                 inputSchema={"type":"object","properties":{"style":{"type":"string","description":"Output style: colon, hyphen, dot, cisco, no_separator","default":"colon","enum":["colon","hyphen","dot","cisco","no_separator"]}},"required":[]}),
            Tool(name="mac_type", description="Classify a MAC address as unicast/multicast and universal/local",
                 inputSchema={"type":"object","properties":{"mac":{"type":"string","description":"MAC address to classify"}},"required":["mac"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        try:
            args = arguments or {}
            if name == "validate_mac":
                cleaned = re.sub(r'[^0-9a-fA-F]', '', args["mac"])
                valid = len(cleaned) == 12
                if valid:
                    patterns = {
                        "colon": bool(re.match(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$', args["mac"])),
                        "hyphen": bool(re.match(r'^([0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2}$', args["mac"])),
                        "dot": bool(re.match(r'^([0-9a-fA-F]{4}\.){2}[0-9a-fA-F]{4}$', args["mac"])),
                        "no_separator": bool(re.match(r'^[0-9a-fA-F]{12}$', args["mac"])),
                    }
                    return [TextContent(type="text", text=json.dumps({
                        "valid": True,
                        "normalized": cleaned,
                        "detected_styles": [k for k, v in patterns.items() if v],
                    }, indent=2))]
                return [TextContent(type="text", text=json.dumps({"valid": False, "normalized": cleaned}, indent=2))]

            if name == "format_mac":
                hex_str = self._normalize(args["mac"])
                style = args["style"]
                result = self._format_mac_raw(hex_str, style)
                return [TextContent(type="text", text=json.dumps({"formatted": result}, indent=2))]

            if name == "lookup_oui":
                hex_str = self._normalize(args["mac"])
                oui = hex_str[:6].upper()
                return [TextContent(type="text", text=json.dumps({
                    "oui": oui,
                    "note": "OUI vendor lookup requires a local vendor database (oui.txt from IEEE). Install it at ~/.mcp/oui.txt to enable lookups.",
                }, indent=2))]

            if name == "generate_mac":
                count = int(args.get("count", 1))
                style = args.get("style", "colon")
                prefix_raw = args.get("prefix", "")
                if prefix_raw:
                    prefix = re.sub(r'[^0-9a-fA-F]', '', prefix_raw)
                    if len(prefix) != 6:
                        raise ValueError(f"Invalid OUI prefix: {prefix_raw} (need exactly 6 hex chars)")
                else:
                    prefix = None
                macs = []
                for _ in range(count):
                    suffix = ''.join(random.choice('0123456789abcdef') for _ in range(6))
                    hex_str = (prefix if prefix else ''.join(random.choice('0123456789abcdef') for _ in range(6))) + suffix
                    macs.append(self._format_mac_raw(hex_str, style))
                return [TextContent(type="text", text=json.dumps({"macs": macs}, indent=2))]

            if name == "mac_info":
                hex_str = self._normalize(args["mac"])
                first_byte = int(hex_str[:2], 16)
                is_multicast = bool(first_byte & 1)
                is_local = bool(first_byte & 2)
                return [TextContent(type="text", text=json.dumps({
                    "mac": args["mac"],
                    "normalized": hex_str,
                    "type": "multicast" if is_multicast else "unicast",
                    "scope": "locally administered" if is_local else "universally administered",
                    "oui": hex_str[:6].upper(),
                    "nic_specific": hex_str[6:],
                }, indent=2))]

            if name == "vendor_search":
                return [TextContent(type="text", text=json.dumps({
                    "query": args["query"],
                    "note": "Vendor search requires a local vendor database (oui.txt from IEEE). Install it at ~/.mcp/oui.txt to enable searches.",
                }, indent=2))]

            if name == "random_mac":
                style = args.get("style", "colon")
                hex_str = ''.join(random.choice('0123456789abcdef') for _ in range(12))
                result = self._format_mac_raw(hex_str, style)
                return [TextContent(type="text", text=json.dumps({"mac": result}, indent=2))]

            if name == "mac_type":
                hex_str = self._normalize(args["mac"])
                first_byte = int(hex_str[:2], 16)
                is_multicast = bool(first_byte & 1)
                is_local = bool(first_byte & 2)
                return [TextContent(type="text", text=json.dumps({
                    "mac": args["mac"],
                    "unicast_multicast": "multicast" if is_multicast else "unicast",
                    "universal_local": "locally administered" if is_local else "universally administered",
                }, indent=2))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    server = MacAddressServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
