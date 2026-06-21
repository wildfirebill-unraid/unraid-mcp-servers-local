import sys
import json
import socket
import ipaddress
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

try:
    from scapy.all import IP, ICMP, TCP, sr1, conf
    conf.verb = 0
    HAS_SCAPY = True
except ImportError:
    HAS_SCAPY = False


class TracerouteServer(Server):
    def __init__(self):
        super().__init__("traceroute")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="trace", description="Perform ICMP traceroute to a host",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "host": {"type": "string", "description": "Destination hostname or IP"},
                         "max_hops": {"type": "integer", "description": "Maximum TTL (default 30)", "default": 30},
                         "timeout": {"type": "number", "description": "Per-hop timeout in seconds (default 3)", "default": 3}
                     },
                     "required": ["host"]
                 }),
            Tool(name="trace_summary", description="Compact traceroute output with RTT per hop",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "host": {"type": "string", "description": "Destination hostname or IP"},
                         "max_hops": {"type": "integer", "description": "Maximum TTL (default 30)", "default": 30}
                     },
                     "required": ["host"]
                 }),
            Tool(name="trace_port", description="TCP-based traceroute to a specific port",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "host": {"type": "string", "description": "Destination hostname or IP"},
                         "port": {"type": "integer", "description": "TCP destination port (default 80)", "default": 80},
                         "max_hops": {"type": "integer", "description": "Maximum TTL (default 30)", "default": 30}
                     },
                     "required": ["host"]
                 }),
            Tool(name="ping_sweep", description="ICMP ping sweep across a network (e.g. 192.168.1.0/24)",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "network": {"type": "string", "description": "CIDR network notation (e.g. 192.168.1.0/24)"}
                     },
                     "required": ["network"]
                 }),
            Tool(name="ping", description="Ping a host with ICMP echo requests",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "host": {"type": "string", "description": "Destination hostname or IP"},
                         "count": {"type": "integer", "description": "Number of pings (default 4)", "default": 4}
                     },
                     "required": ["host"]
                 }),
        ]

    def _trace(self, host: str, max_hops: int, timeout: float) -> list:
        if not HAS_SCAPY:
            return [{"error": "scapy not installed"}]
        try:
            dst_ip = socket.gethostbyname(host)
        except socket.gaierror as e:
            return [{"error": f"Cannot resolve {host}: {e}"}]
        hops = []
        for ttl in range(1, max_hops + 1):
            pkt = IP(dst=dst_ip, ttl=ttl) / ICMP()
            reply = sr1(pkt, timeout=timeout, verbose=0)
            if reply is None:
                hops.append({"hop": ttl, "ip": None, "rtt_ms": None, "status": "timeout"})
            else:
                rtt = (reply.time - pkt.sent_time) * 1000
                hops.append({
                    "hop": ttl,
                    "ip": reply.src,
                    "rtt_ms": round(rtt, 2),
                    "status": "reachable"
                })
                if reply.src == dst_ip:
                    break
        return hops

    def _trace_tcp(self, host: str, port: int, max_hops: int) -> list:
        if not HAS_SCAPY:
            return [{"error": "scapy not installed"}]
        try:
            dst_ip = socket.gethostbyname(host)
        except socket.gaierror as e:
            return [{"error": f"Cannot resolve {host}: {e}"}]
        hops = []
        for ttl in range(1, max_hops + 1):
            pkt = IP(dst=dst_ip, ttl=ttl) / TCP(dport=port, flags="S")
            reply = sr1(pkt, timeout=3, verbose=0)
            if reply is None:
                hops.append({"hop": ttl, "ip": None, "rtt_ms": None, "status": "timeout"})
            else:
                rtt = (reply.time - pkt.sent_time) * 1000
                hops.append({
                    "hop": ttl,
                    "ip": reply.src,
                    "rtt_ms": round(rtt, 2),
                    "status": "reachable"
                })
                if reply.haslayer(TCP) and reply.getlayer(TCP).flags & 0x12:
                    break
        return hops

    def _ping(self, host: str, count: int) -> dict:
        if not HAS_SCAPY:
            return {"error": "scapy not installed"}
        try:
            dst_ip = socket.gethostbyname(host)
        except socket.gaierror as e:
            return {"error": f"Cannot resolve {host}: {e}"}
        results = []
        sent = 0
        received = 0
        rtts = []
        for i in range(count):
            pkt = IP(dst=dst_ip) / ICMP()
            reply = sr1(pkt, timeout=3, verbose=0)
            sent += 1
            if reply is None:
                results.append({"seq": i + 1, "status": "timeout"})
            else:
                rtt = (reply.time - pkt.sent_time) * 1000
                rtts.append(rtt)
                received += 1
                results.append({"seq": i + 1, "ip": reply.src, "rtt_ms": round(rtt, 2), "status": "success"})
        stats = {
            "host": host,
            "ip": dst_ip,
            "sent": sent,
            "received": received,
            "loss_pct": round((sent - received) / sent * 100, 1) if sent else 0,
        }
        if rtts:
            stats["rtt_min_ms"] = round(min(rtts), 2)
            stats["rtt_max_ms"] = round(max(rtts), 2)
            stats["rtt_avg_ms"] = round(sum(rtts) / len(rtts), 2)
        stats["results"] = results
        return stats

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}

        if not HAS_SCAPY:
            return [TextContent(type="text", text=json.dumps({
                "error": "scapy is not installed. Install with: pip install scapy",
                "note": "This server also requires --cap-add=NET_RAW (Docker) or root on Linux"
            }, indent=2))]

        if name == "trace":
            host = args["host"]
            max_hops = int(args.get("max_hops", 30))
            timeout = float(args.get("timeout", 3))
            hops = await anyio.to_thread.run_sync(self._trace, host, max_hops, timeout)
            return [TextContent(type="text", text=json.dumps(hops, indent=2))]

        if name == "trace_summary":
            host = args["host"]
            max_hops = int(args.get("max_hops", 30))
            hops = await anyio.to_thread.run_sync(self._trace, host, max_hops, 3)
            lines = [f"traceroute to {host}"]
            for h in hops:
                if h.get("ip"):
                    lines.append(f"  {h['hop']:2d}  {h['ip']:15s}  {h['rtt_ms']:>8.2f} ms")
                else:
                    lines.append(f"  {h['hop']:2d}  *  timeout")
            if hops:
                last = hops[-1]
                if last.get("ip"):
                    lines.append(f"Destination reached at hop {last['hop']}")
            return [TextContent(type="text", text="\n".join(lines))]

        if name == "trace_port":
            host = args["host"]
            port = int(args.get("port", 80))
            max_hops = int(args.get("max_hops", 30))
            hops = await anyio.to_thread.run_sync(self._trace_tcp, host, port, max_hops)
            return [TextContent(type="text", text=json.dumps(hops, indent=2))]

        if name == "ping_sweep":
            network_str = args["network"]
            try:
                network = ipaddress.ip_network(network_str, strict=False)
            except ValueError as e:
                return [TextContent(type="text", text=json.dumps({"error": f"Invalid network: {e}"}))]
            results = []
            for ip in network.hosts():
                pkt = IP(dst=str(ip)) / ICMP()
                reply = sr1(pkt, timeout=1, verbose=0)
                if reply is not None:
                    results.append({"ip": str(ip), "status": "alive"})
            return [TextContent(type="text", text=json.dumps({
                "network": network_str,
                "alive_count": len(results),
                "hosts": results
            }, indent=2))]

        if name == "ping":
            host = args["host"]
            count = int(args.get("count", 4))
            stats = await anyio.to_thread.run_sync(self._ping, host, count)
            return [TextContent(type="text", text=json.dumps(stats, indent=2))]

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    server = TracerouteServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
