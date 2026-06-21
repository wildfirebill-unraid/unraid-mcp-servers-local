import sys
import json
import os
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

try:
    import nmap
except ImportError:
    nmap = None


COMMON_OPTIONS = {
    "quick": "-T4 -F",
    "intense": "-T4 -A -v",
    "ping": "-sn",
    "version": "-sV",
    "os": "-O",
    "default": "-sS -sV -T4",
}


class NmapLiteServer(Server):
    def __init__(self):
        super().__init__("nmap-lite")
        self._scanner = None
        self._last_results: dict[str, Any] = {}

    def _get_scanner(self):
        if nmap is None:
            raise RuntimeError("python-nmap is not installed")
        if self._scanner is None:
            self._scanner = nmap.PortScanner()
        return self._scanner

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="scan_host",
                description="Scan a single host with custom ports and arguments",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "host": {"type": "string", "description": "IP or hostname"},
                        "ports": {"type": "string", "description": "Port specification (e.g. '22-443' or '22,80,443')"},
                        "arguments": {"type": "string", "description": "Nmap arguments (e.g. '-sS -sV -T4')"}
                    },
                    "required": ["host"]
                }
            ),
            Tool(
                name="scan_network",
                description="Scan a CIDR network range",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "network": {"type": "string", "description": "CIDR notation (e.g. '192.168.1.0/24')"},
                        "ports": {"type": "string", "description": "Port specification"},
                        "arguments": {"type": "string", "description": "Nmap arguments"}
                    },
                    "required": ["network"]
                }
            ),
            Tool(
                name="quick_scan",
                description="Quick scan of common ports on a host",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "host": {"type": "string", "description": "IP or hostname"}
                    },
                    "required": ["host"]
                }
            ),
            Tool(
                name="os_detection",
                description="OS fingerprint scan (may require root privileges)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "host": {"type": "string", "description": "IP or hostname"}
                    },
                    "required": ["host"]
                }
            ),
            Tool(
                name="service_detection",
                description="Service version detection scan",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "host": {"type": "string", "description": "IP or hostname"},
                        "ports": {"type": "string", "description": "Port specification"}
                    },
                    "required": ["host"]
                }
            ),
            Tool(
                name="scan_result",
                description="Get the last scan result for a given host",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "host": {"type": "string", "description": "IP or hostname"}
                    },
                    "required": ["host"]
                }
            ),
            Tool(
                name="list_scan_options",
                description="List common nmap scan arguments and their descriptions",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
        ]

    def _run_scan(self, host: str, ports: str | None = None, arguments: str | None = None) -> dict[str, Any]:
        nm = self._get_scanner()
        kwargs: dict[str, Any] = {}
        if ports:
            kwargs["ports"] = ports
        if arguments:
            kwargs["arguments"] = arguments
        try:
            info = nm.scan(host, **kwargs)
        except Exception as e:
            raise RuntimeError(f"scan failed: {e}")
        host_key = host
        if host_key not in info.get("scan", {}):
            for h in info.get("scan", {}):
                host_key = h
                break
        self._last_results[host] = info
        result = info.get("scan", {}).get(host_key, {})
        return {
            "host": host_key,
            "hostname": result.get("hostnames", [{}])[0].get("name", "") if result.get("hostnames") else "",
            "state": result.get("status", {}).get("state", "unknown"),
            "protocols": list(result.get("protocols", [])),
            "ports": [
                {
                    "port": p,
                    "state": data.get("state", ""),
                    "name": data.get("name", ""),
                    "product": data.get("product", ""),
                    "version": data.get("version", ""),
                    "protocol": proto,
                }
                for proto in result.get("protocols", [])
                for p, data in result.get(proto, {}).items()
            ],
            "osmatch": result.get("osmatch", []),
            "raw": info,
        }

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "scan_host":
                host = args["host"]
                ports = args.get("ports")
                scan_args = args.get("arguments")
                data = self._run_scan(host, ports, scan_args)
                return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]

            elif name == "scan_network":
                network = args["network"]
                ports = args.get("ports")
                scan_args = args.get("arguments")
                data = self._run_scan(network, ports, scan_args)
                return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]

            elif name == "quick_scan":
                host = args["host"]
                data = self._run_scan(host, arguments=COMMON_OPTIONS["quick"])
                return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]

            elif name == "os_detection":
                host = args["host"]
                data = self._run_scan(host, arguments=COMMON_OPTIONS["os"])
                return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]

            elif name == "service_detection":
                host = args["host"]
                ports = args.get("ports")
                data = self._run_scan(host, ports, arguments=COMMON_OPTIONS["version"])
                return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]

            elif name == "scan_result":
                host = args["host"]
                result = self._last_results.get(host)
                if result:
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                return [TextContent(type="text", text=json.dumps({"error": f"no cached scan for {host}"}, indent=2))]

            elif name == "list_scan_options":
                return [TextContent(type="text", text=json.dumps(COMMON_OPTIONS, indent=2))]

            raise ValueError(f"Unknown tool: {name}")
        except RuntimeError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = NmapLiteServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
