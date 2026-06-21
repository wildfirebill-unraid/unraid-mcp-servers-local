import sys
import json
import socket
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

RECORD_TYPES = {
    "A": "IPv4 address resolution (supported via socket.getaddrinfo)",
    "AAAA": "IPv6 address resolution (supported via socket.getaddrinfo)",
    "PTR": "Reverse DNS lookup (supported via socket.gethostbyaddr)",
    "MX": "Mail exchange records (requires dnspython library)",
    "NS": "Nameserver records (requires dnspython library)",
    "CNAME": "Canonical name records (requires dnspython library)",
    "SOA": "Start of Authority records (requires dnspython library)",
    "TXT": "Text records (requires dnspython library)",
    "SRV": "Service records (requires dnspython library)"
}

NEEDS_DNSPYTHON_MSG = "This record type requires the 'dnspython' library. Install with: pip install dnspython"

class DnsResolverServer(Server):
    def __init__(self):
        super().__init__("dns-resolver")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="resolve_hostname", description="Resolve a hostname to IPv4/IPv6 addresses",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "hostname": {"type": "string", "description": "Hostname to resolve (e.g. example.com)"}
                     },
                     "required": ["hostname"]
                 }),
            Tool(name="resolve_ip", description="Reverse DNS lookup - resolve IP address to hostname",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "ip_address": {"type": "string", "description": "IP address to reverse look up"}
                     },
                     "required": ["ip_address"]
                 }),
            Tool(name="get_mx_record", description="Get MX records for a domain (requires dnspython)",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "domain": {"type": "string", "description": "Domain name"}
                     },
                     "required": ["domain"]
                 }),
            Tool(name="dns_lookup", description="Generic DNS lookup wrapper (A/AAAA/PTR supported natively)",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "hostname": {"type": "string", "description": "Hostname or IP address"},
                         "record_type": {"type": "string", "description": "Record type: A, AAAA, or PTR", "default": "A"}
                     },
                     "required": ["hostname"]
                 }),
            Tool(name="list_record_types", description="List supported DNS record types and their availability",
                 inputSchema={
                     "type": "object",
                     "properties": {}
                 }),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}

        if name == "resolve_hostname":
            hostname = args["hostname"]
            try:
                addresses = await anyio.to_thread.run_sync(
                    socket.getaddrinfo, hostname, None
                )
                ipv4 = set()
                ipv6 = set()
                for addr in addresses:
                    ip = addr[4][0]
                    if addr[0] == socket.AF_INET:
                        ipv4.add(ip)
                    elif addr[0] == socket.AF_INET6:
                        ipv6.add(ip)
                result = {
                    "hostname": hostname,
                    "ipv4": sorted(ipv4) if ipv4 else [],
                    "ipv6": sorted(ipv6) if ipv6 else [],
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except socket.gaierror as e:
                return [TextContent(type="text", text=json.dumps({
                    "hostname": hostname, "error": f"DNS resolution failed: {e}"
                }))]

        if name == "resolve_ip":
            ip_address = args["ip_address"]
            try:
                hostname = await anyio.to_thread.run_sync(
                    socket.gethostbyaddr, ip_address
                )
                result = {
                    "ip_address": ip_address,
                    "hostname": hostname[0],
                    "aliases": hostname[1] if hostname[1] else []
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except socket.herror as e:
                return [TextContent(type="text", text=json.dumps({
                    "ip_address": ip_address, "error": f"Reverse lookup failed: {e}"
                }))]
            except socket.gaierror as e:
                return [TextContent(type="text", text=json.dumps({
                    "ip_address": ip_address, "error": str(e)
                }))]

        if name == "get_mx_record":
            domain = args["domain"]
            return [TextContent(type="text", text=json.dumps({
                "domain": domain,
                "note": NEEDS_DNSPYTHON_MSG,
                "example": f"import dns.resolver; answers = dns.resolver.resolve('{domain}', 'MX')"
            }, indent=2))]

        if name == "dns_lookup":
            hostname = args["hostname"]
            record_type = args.get("record_type", "A").upper()
            if record_type == "A":
                try:
                    addrs = await anyio.to_thread.run_sync(
                        socket.getaddrinfo, hostname, None, socket.AF_INET
                    )
                    ips = sorted(set(a[4][0] for a in addrs))
                    return [TextContent(type="text", text=json.dumps({
                        "hostname": hostname, "type": "A", "records": ips
                    }, indent=2))]
                except socket.gaierror as e:
                    return [TextContent(type="text", text=json.dumps({
                        "hostname": hostname, "type": "A", "error": str(e)
                    }))]
            elif record_type == "AAAA":
                try:
                    addrs = await anyio.to_thread.run_sync(
                        socket.getaddrinfo, hostname, None, socket.AF_INET6
                    )
                    ips = sorted(set(a[4][0] for a in addrs))
                    return [TextContent(type="text", text=json.dumps({
                        "hostname": hostname, "type": "AAAA", "records": ips
                    }, indent=2))]
                except socket.gaierror as e:
                    return [TextContent(type="text", text=json.dumps({
                        "hostname": hostname, "type": "AAAA", "error": str(e)
                    }))]
            elif record_type == "PTR":
                try:
                    hostname_res = await anyio.to_thread.run_sync(
                        socket.gethostbyaddr, hostname
                    )
                    return [TextContent(type="text", text=json.dumps({
                        "ip": hostname, "type": "PTR", "hostname": hostname_res[0]
                    }, indent=2))]
                except (socket.herror, socket.gaierror) as e:
                    return [TextContent(type="text", text=json.dumps({
                        "ip": hostname, "type": "PTR", "error": str(e)
                    }))]
            else:
                return [TextContent(type="text", text=json.dumps({
                    "hostname": hostname,
                    "record_type": record_type,
                    "note": NEEDS_DNSPYTHON_MSG
                }))]

        if name == "list_record_types":
            return [TextContent(type="text", text=json.dumps(RECORD_TYPES, indent=2))]

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    server = DnsResolverServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
