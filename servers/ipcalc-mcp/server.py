import os
import json
import ipaddress
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("ipcalc-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="subnet_info",
            description="Get subnet information for a CIDR notation",
            inputSchema={
                "type": "object",
                "properties": {
                    "network": {"type": "string", "description": "CIDR notation (e.g. 192.168.1.0/24)"}
                },
                "required": ["network"]
            }
        ),
        Tool(
            name="ip_to_int",
            description="Convert an IP address to an integer",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IP address (e.g. 192.168.1.1)"}
                },
                "required": ["ip"]
            }
        ),
        Tool(
            name="int_to_ip",
            description="Convert an integer to an IP address",
            inputSchema={
                "type": "object",
                "properties": {
                    "number": {"type": "integer", "description": "Integer representation of an IP"}
                },
                "required": ["number"]
            }
        ),
        Tool(
            name="cidr_contains",
            description="Check if a CIDR range contains an IP address",
            inputSchema={
                "type": "object",
                "properties": {
                    "cidr": {"type": "string", "description": "CIDR notation"},
                    "ip": {"type": "string", "description": "IP address to check"}
                },
                "required": ["cidr", "ip"]
            }
        ),
        Tool(
            name="cidr_list_hosts",
            description="List hosts in a CIDR range (for small ranges)",
            inputSchema={
                "type": "object",
                "properties": {
                    "cidr": {"type": "string", "description": "CIDR notation"},
                    "limit": {"type": "integer", "description": "Max hosts to return (default 10)"}
                },
                "required": ["cidr"]
            }
        ),
        Tool(
            name="merge_cidrs",
            description="Merge overlapping or adjacent CIDR ranges",
            inputSchema={
                "type": "object",
                "properties": {
                    "cidrs": {"type": "array", "items": {"type": "string"}, "description": "List of CIDR notations"}
                },
                "required": ["cidrs"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "subnet_info":
        net = ipaddress.ip_network(arguments["network"], strict=False)
        hosts = list(net.hosts())
        result = json.dumps({
            "network_address": str(net.network_address),
            "broadcast": str(net.broadcast_address),
            "netmask": str(net.netmask),
            "wildcard": str(net.hostmask),
            "first_host": str(hosts[0]) if hosts else None,
            "last_host": str(hosts[-1]) if hosts else None,
            "host_count": net.num_addresses - 2 if net.num_addresses > 2 else net.num_addresses,
            "prefix_length": net.prefixlen
        })
    elif name == "ip_to_int":
        result = str(int(ipaddress.ip_address(arguments["ip"])))
    elif name == "int_to_ip":
        result = str(ipaddress.ip_address(arguments["number"]))
    elif name == "cidr_contains":
        net = ipaddress.ip_network(arguments["cidr"], strict=False)
        ip = ipaddress.ip_address(arguments["ip"])
        result = json.dumps({"contains": ip in net})
    elif name == "cidr_list_hosts":
        net = ipaddress.ip_network(arguments["cidr"], strict=False)
        limit = arguments.get("limit", 10)
        hosts = [str(h) for h in list(net.hosts())[:limit]]
        total = net.num_addresses - 2 if net.num_addresses > 2 else net.num_addresses
        result = json.dumps({"hosts": hosts, "total": total, "returned": len(hosts), "truncated": len(hosts) < total})
    elif name == "merge_cidrs":
        nets = sorted([ipaddress.ip_network(c, strict=False) for c in arguments["cidrs"]],
                      key=lambda n: (n.network_address, n.prefixlen))
        merged = [nets[0]]
        for net in nets[1:]:
            if net.network_address <= merged[-1].broadcast_address:
                supernet = merged[-1].supernet()
                if net.subnet_of(supernet):
                    continue
                merged[-1] = ipaddress.ip_network(
                    f"{merged[-1].network_address}/{min(merged[-1].prefixlen, net.prefixlen)}",
                    strict=False
                )
            else:
                merged.append(net)
        result = json.dumps({"merged": [str(n) for n in merged]})
    else:
        raise ValueError(f"Unknown tool: {name}")
    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ipcalc-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
