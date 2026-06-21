import os
import socket
import subprocess
import platform
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("check-host-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="dns_lookup",
            description="Resolve a hostname to IP addresses",
            inputSchema={
                "type": "object",
                "properties": {
                    "hostname": {"type": "string", "description": "Hostname to resolve (e.g. google.com)"}
                },
                "required": ["hostname"]
            }
        ),
        Tool(
            name="ping_host",
            description="Ping a host and return latency stats",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Hostname or IP to ping"},
                    "count": {"type": "integer", "description": "Number of pings (default 3)"}
                },
                "required": ["host"]
            }
        ),
        Tool(
            name="check_port",
            description="Check if a TCP port is open on a host",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Hostname or IP"},
                    "port": {"type": "integer", "description": "TCP port number"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 5)"}
                },
                "required": ["host", "port"]
            }
        ),
        Tool(
            name="http_check",
            description="Perform an HTTP GET check and return status code and timing",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to check (e.g. https://example.com)"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 10)"}
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="reverse_dns",
            description="Perform a reverse DNS lookup on an IP address",
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "IP address to look up"}
                },
                "required": ["ip"]
            }
        ),
        Tool(
            name="whois_query",
            description="Perform a basic WHOIS lookup (requires whois command)",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Domain name to query"}
                },
                "required": ["domain"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = ""

    if name == "dns_lookup":
        try:
            addrs = socket.getaddrinfo(arguments["hostname"], 0)
            ips = sorted(set(a[4][0] for a in addrs))
            result = str({"hostname": arguments["hostname"], "addresses": ips})
        except socket.gaierror as e:
            result = str({"error": str(e)})

    elif name == "ping_host":
        host = arguments["host"]
        count = arguments.get("count", 3)
        param = "-n" if platform.system().lower() == "windows" else "-c"
        try:
            proc = subprocess.run(
                ["ping", param, str(count), host],
                capture_output=True, text=True, timeout=30
            )
            result = proc.stdout + "\n" + proc.stderr
        except subprocess.TimeoutExpired:
            result = "Ping timed out"
        except FileNotFoundError:
            result = "Ping command not found in container"

    elif name == "check_port":
        host = arguments["host"]
        port = arguments["port"]
        timeout = arguments.get("timeout", 5)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            start = __import__("time").time()
            s.connect((host, port))
            elapsed = round((__import__("time").time() - start) * 1000, 2)
            s.close()
            result = str({"host": host, "port": port, "open": True, "latency_ms": elapsed})
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            result = str({"host": host, "port": port, "open": False, "error": str(e)})

    elif name == "http_check":
        try:
            import httpx
            url = arguments["url"]
            timeout = arguments.get("timeout", 10)
            start = __import__("time").time()
            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
            elapsed = round((__import__("time").time() - start) * 1000, 2)
            result = str({
                "url": url,
                "status_code": resp.status_code,
                "elapsed_ms": elapsed,
                "headers": dict(resp.headers),
                "body_preview": resp.text[:500],
            })
        except Exception as e:
            result = str({"error": str(e)})

    elif name == "reverse_dns":
        try:
            hostname, aliases, ips = socket.gethostbyaddr(arguments["ip"])
            result = str({"ip": arguments["ip"], "hostname": hostname, "aliases": aliases})
        except socket.herror as e:
            result = str({"error": str(e)})

    elif name == "whois_query":
        try:
            proc = subprocess.run(
                ["whois", arguments["domain"]],
                capture_output=True, text=True, timeout=15
            )
            result = proc.stdout[:2000] + ("\n...[truncated]" if len(proc.stdout) > 2000 else "")
        except FileNotFoundError:
            result = "whois command not found in container"
        except subprocess.TimeoutExpired:
            result = "whois query timed out"

    else:
        raise ValueError(f"Unknown tool: {name}")

    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="check-host-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
