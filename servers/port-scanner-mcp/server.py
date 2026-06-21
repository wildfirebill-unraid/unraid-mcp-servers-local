import sys
import json
import socket
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 6379: "Redis",
    8080: "HTTP-alt", 8443: "HTTPS-alt", 27017: "MongoDB"
}

PORT_INFO = {
    20: "FTP data transfer", 21: "FTP control (File Transfer Protocol)",
    22: "SSH (Secure Shell) remote login", 23: "Telnet (unencrypted remote terminal)",
    25: "SMTP (Simple Mail Transfer Protocol)", 53: "DNS (Domain Name System)",
    67: "DHCP/BOOTP server", 68: "DHCP/BOOTP client",
    69: "TFTP (Trivial File Transfer Protocol)", 80: "HTTP (Hypertext Transfer Protocol)",
    110: "POP3 (Post Office Protocol v3)", 123: "NTP (Network Time Protocol)",
    137: "NetBIOS name service", 138: "NetBIOS datagram", 139: "NetBIOS session",
    143: "IMAP (Internet Message Access Protocol)", 161: "SNMP agent",
    162: "SNMP trap", 179: "BGP (Border Gateway Protocol)",
    194: "IRC (Internet Relay Chat)", 389: "LDAP (Lightweight Directory Access Protocol)",
    443: "HTTPS (HTTP over TLS)", 445: "SMB (Server Message Block)",
    465: "SMTPS (SMTP over SSL)", 514: "Syslog", 587: "SMTP submission",
    636: "LDAPS (LDAP over SSL)", 993: "IMAPS (IMAP over SSL)",
    995: "POP3S (POP3 over SSL)", 1433: "Microsoft SQL Server",
    1521: "Oracle DB", 2049: "NFS (Network File System)",
    2375: "Docker REST API (plain)", 2376: "Docker REST API (TLS)",
    3306: "MySQL/MariaDB database", 3389: "RDP (Remote Desktop Protocol)",
    4333: "Ohai (local llm)", 5432: "PostgreSQL database",
    5900: "VNC (Virtual Network Computing)", 5901: "VNC display :1",
    6379: "Redis key-value store", 6443: "Kubernetes API (HTTPS)",
    8080: "HTTP alternate (proxy/cache)", 8443: "HTTPS alternate",
    9090: "Prometheus / HTTP admin", 11211: "Memcached",
    27017: "MongoDB database", 28017: "MongoDB web admin",
    5000: "Flask / HTTP alt", 5001: "Syncthing web UI"
}

class PortScannerServer(Server):
    def __init__(self):
        super().__init__("port-scanner")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="scan_port", description="Scan a single TCP port on a host",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "host": {"type": "string", "description": "Hostname or IP address"},
                         "port": {"type": "integer", "description": "TCP port number (1-65535)"},
                         "timeout": {"type": "number", "description": "Connection timeout in seconds", "default": 2}
                     },
                     "required": ["host", "port"]
                 }),
            Tool(name="scan_ports", description="Scan multiple specific TCP ports on a host",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "host": {"type": "string", "description": "Hostname or IP address"},
                         "ports_list": {"type": "string", "description": "Comma-separated port numbers (e.g. '22,80,443')"},
                         "timeout": {"type": "number", "description": "Connection timeout in seconds", "default": 2}
                     },
                     "required": ["host", "ports_list"]
                 }),
            Tool(name="scan_range", description="Scan a range of TCP ports on a host",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "host": {"type": "string", "description": "Hostname or IP address"},
                         "start_port": {"type": "integer", "description": "Starting port (1-65535)"},
                         "end_port": {"type": "integer", "description": "Ending port (1-65535)"},
                         "timeout": {"type": "number", "description": "Connection timeout in seconds", "default": 2}
                     },
                     "required": ["host", "start_port", "end_port"]
                 }),
            Tool(name="scan_common", description="Scan 20 common TCP ports on a host",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "host": {"type": "string", "description": "Hostname or IP address"},
                         "timeout": {"type": "number", "description": "Connection timeout in seconds", "default": 2}
                     },
                     "required": ["host"]
                 }),
            Tool(name="port_info", description="Get description of a well-known port",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "port": {"type": "integer", "description": "Port number"}
                     },
                     "required": ["port"]
                 }),
            Tool(name="list_common_ports", description="List common ports with their service names",
                 inputSchema={
                     "type": "object",
                     "properties": {}
                 }),
        ]

    def _scan_port(self, host: str, port: int, timeout: float) -> dict:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            service = PORT_INFO.get(port, "Unknown")
            return {"port": port, "service": service, "state": "open" if result == 0 else "closed"}
        except socket.gaierror as e:
            return {"port": port, "error": f"DNS resolution failed: {e}"}
        except socket.timeout:
            return {"port": port, "state": "filtered", "service": PORT_INFO.get(port, "Unknown")}
        except Exception as e:
            return {"port": port, "error": str(e)}

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}

        if name == "scan_port":
            host = args["host"]
            port = int(args["port"])
            timeout = float(args.get("timeout", 2))
            result = await anyio.to_thread.run_sync(self._scan_port, host, port, timeout)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "scan_ports":
            host = args["host"]
            timeout = float(args.get("timeout", 2))
            ports = [int(p.strip()) for p in args["ports_list"].split(",") if p.strip()]
            results = []
            for p in ports:
                r = await anyio.to_thread.run_sync(self._scan_port, host, p, timeout)
                results.append(r)
            return [TextContent(type="text", text=json.dumps(results, indent=2))]

        if name == "scan_range":
            host = args["host"]
            start = int(args["start_port"])
            end = int(args["end_port"])
            timeout = float(args.get("timeout", 2))
            if start > end or start < 1 or end > 65535:
                raise ValueError("Invalid port range (1-65535)")
            if end - start > 1000:
                return [TextContent(type="text", text=json.dumps({"error": "Range too large (max 1000 ports)"}))]
            results = []
            for p in range(start, end + 1):
                r = await anyio.to_thread.run_sync(self._scan_port, host, p, timeout)
                results.append(r)
            return [TextContent(type="text", text=json.dumps(results, indent=2))]

        if name == "scan_common":
            host = args["host"]
            timeout = float(args.get("timeout", 2))
            results = []
            for p in COMMON_PORTS:
                r = await anyio.to_thread.run_sync(self._scan_port, host, p, timeout)
                results.append(r)
            open_ports = [r for r in results if r.get("state") == "open"]
            summary = {
                "target": host,
                "total_scanned": len(COMMON_PORTS),
                "open_count": len(open_ports),
                "open_ports": open_ports,
                "all_results": results
            }
            return [TextContent(type="text", text=json.dumps(summary, indent=2))]

        if name == "port_info":
            port = int(args["port"])
            info = PORT_INFO.get(port, f"Port {port} is not in the well-known ports database")
            return [TextContent(type="text", text=json.dumps({"port": port, "description": info}))]

        if name == "list_common_ports":
            ports_list = [{"port": p, "service": s} for p, s in COMMON_PORTS.items()]
            return [TextContent(type="text", text=json.dumps(ports_list, indent=2))]

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    server = PortScannerServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
