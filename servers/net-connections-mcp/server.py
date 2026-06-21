import sys
import json
import os
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

CONN_STATES = {
    psutil.CONN_ESTABLISHED: "ESTABLISHED",
    psutil.CONN_SYN_SENT: "SYN_SENT",
    psutil.CONN_SYN_RECV: "SYN_RECV",
    psutil.CONN_FIN_WAIT1: "FIN_WAIT1",
    psutil.CONN_FIN_WAIT2: "FIN_WAIT2",
    psutil.CONN_TIME_WAIT: "TIME_WAIT",
    psutil.CONN_CLOSE: "CLOSE",
    psutil.CONN_CLOSE_WAIT: "CLOSE_WAIT",
    psutil.CONN_LAST_ACK: "LAST_ACK",
    psutil.CONN_LISTEN: "LISTEN",
    psutil.CONN_CLOSING: "CLOSING",
    psutil.CONN_NONE: "NONE",
}

class NetConnectionsServer(Server):
    def __init__(self):
        super().__init__("net-connections")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="list_connections", description="List network connections",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "kind": {
                             "type": "string",
                             "description": "Connection kind: inet (default), tcp, tcp4, tcp6, udp, udp4, udp6, unix, all",
                             "default": "inet"
                         }
                     }
                 }),
            Tool(name="connection_stats", description="Count connections grouped by state",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "kind": {
                             "type": "string",
                             "description": "Connection kind: inet (default), tcp, tcp4, tcp6, udp, unix, all",
                             "default": "inet"
                         }
                     }
                 }),
            Tool(name="list_listeners", description="List all listening ports and services",
                 inputSchema={
                     "type": "object",
                     "properties": {}
                 }),
            Tool(name="connection_detail", description="Show network connections for a specific PID",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "pid": {"type": "integer", "description": "Process ID"}
                     },
                     "required": ["pid"]
                 }),
            Tool(name="network_io_counters", description="Show bytes/packets in/out per network interface",
                 inputSchema={
                     "type": "object",
                     "properties": {}
                 }),
            Tool(name="get_default_gateway", description="Show default gateway and interface information",
                 inputSchema={
                     "type": "object",
                     "properties": {}
                 }),
        ]

    def _format_conn(self, conn) -> dict:
        laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
        raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
        state = CONN_STATES.get(conn.status, str(conn.status))
        proc_name = ""
        if conn.pid and conn.pid > 0:
            try:
                proc = psutil.Process(conn.pid)
                proc_name = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_name = ""
        return {
            "fd": conn.fd,
            "family": str(conn.family),
            "type": str(conn.type),
            "local_addr": laddr,
            "remote_addr": raddr,
            "state": state,
            "pid": conn.pid,
            "process": proc_name
        }

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}

        if not HAS_PSUTIL:
            return [TextContent(type="text", text=json.dumps({
                "error": "psutil is not installed. Install with: pip install psutil"
            }, indent=2))]

        if name == "list_connections":
            kind = args.get("kind", "inet")
            connections = await anyio.to_thread.run_sync(
                psutil.net_connections, kind
            )
            result = [self._format_conn(c) for c in connections]
            return [TextContent(type="text", text=json.dumps({
                "kind": kind,
                "total": len(result),
                "connections": result
            }, indent=2))]

        if name == "connection_stats":
            kind = args.get("kind", "inet")
            connections = await anyio.to_thread.run_sync(
                psutil.net_connections, kind
            )
            state_count = {}
            for c in connections:
                state = CONN_STATES.get(c.status, str(c.status))
                state_count[state] = state_count.get(state, 0) + 1
            return [TextContent(type="text", text=json.dumps({
                "kind": kind,
                "total": len(connections),
                "by_state": state_count
            }, indent=2))]

        if name == "list_listeners":
            connections = await anyio.to_thread.run_sync(
                psutil.net_connections, "inet"
            )
            listeners = []
            for c in connections:
                if c.status == psutil.CONN_LISTEN and c.laddr:
                    proc_name = ""
                    if c.pid and c.pid > 0:
                        try:
                            proc = psutil.Process(c.pid)
                            proc_name = proc.name()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            proc_name = ""
                    listeners.append({
                        "port": c.laddr.port,
                        "ip": c.laddr.ip,
                        "pid": c.pid,
                        "process": proc_name,
                        "family": "IPv6" if c.family == 10 else "IPv4"
                    })
            listeners.sort(key=lambda x: x["port"])
            return [TextContent(type="text", text=json.dumps({
                "total_listeners": len(listeners),
                "listeners": listeners
            }, indent=2))]

        if name == "connection_detail":
            pid = int(args["pid"])
            if pid <= 0:
                return [TextContent(type="text", text=json.dumps({"error": "Invalid PID"}))]
            try:
                proc = await anyio.to_thread.run_sync(psutil.Process, pid)
                proc_name = proc.name()
            except psutil.NoSuchProcess:
                return [TextContent(type="text", text=json.dumps({"error": f"No process with PID {pid}"}))]
            connections = await anyio.to_thread.run_sync(
                psutil.net_connections, "inet"
            )
            proc_conns = [self._format_conn(c) for c in connections if c.pid == pid]
            return [TextContent(type="text", text=json.dumps({
                "pid": pid,
                "process": proc_name,
                "total_connections": len(proc_conns),
                "connections": proc_conns
            }, indent=2))]

        if name == "network_io_counters":
            counters = await anyio.to_thread.run_sync(psutil.net_io_counters, pernic=True)
            addrs = await anyio.to_thread.run_sync(psutil.net_if_addrs)
            interfaces = []
            for iface, stats in counters.items():
                addrs_str = []
                if iface in addrs:
                    for a in addrs[iface]:
                        if a.address:
                            addrs_str.append(a.address)
                interfaces.append({
                    "interface": iface,
                    "bytes_sent": stats.bytes_sent,
                    "bytes_recv": stats.bytes_recv,
                    "packets_sent": stats.packets_sent,
                    "packets_recv": stats.packets_recv,
                    "errin": stats.errin,
                    "errout": stats.errout,
                    "dropin": stats.dropin,
                    "dropout": stats.dropout,
                    "addresses": addrs_str
                })
            total = await anyio.to_thread.run_sync(psutil.net_io_counters, pernic=False)
            return [TextContent(type="text", text=json.dumps({
                "interfaces": interfaces,
                "total_bytes_sent": total.bytes_sent,
                "total_bytes_recv": total.bytes_recv
            }, indent=2))]

        if name == "get_default_gateway":
            try:
                if_stats = await anyio.to_thread.run_sync(psutil.net_if_stats)
                addrs = await anyio.to_thread.run_sync(psutil.net_if_addrs)
                gateways = {}
                default_gw = ""
                if os.path.exists("/proc/net/route"):
                    with open("/proc/net/route") as f:
                        lines = f.readlines()[1:]
                        for line in lines:
                            parts = line.split()
                            if len(parts) >= 4:
                                iface = parts[0]
                                dest_hex = parts[1]
                                gw_hex = parts[2]
                                if dest_hex == "00000000" and gw_hex != "00000000":
                                    gw_int = int(gw_hex, 16)
                                    gw_ip = ".".join([
                                        str((gw_int >> 0) & 0xFF),
                                        str((gw_int >> 8) & 0xFF),
                                        str((gw_int >> 16) & 0xFF),
                                        str((gw_int >> 24) & 0xFF),
                                    ])
                                    default_gw = gw_ip
                                    gateways[iface] = {"gateway": gw_ip}
                interfaces_info = []
                for iface, stats in if_stats.items():
                    iface_addrs = addrs.get(iface, [])
                    ips = [a.address for a in iface_addrs if a.address]
                    gw = gateways.get(iface, {}).get("gateway", "")
                    interfaces_info.append({
                        "interface": iface,
                        "isup": stats.isup,
                        "speed_mbps": stats.speed,
                        "addresses": ips,
                        "gateway": gw
                    })
                return [TextContent(type="text", text=json.dumps({
                    "default_gateway": default_gw,
                    "interfaces": interfaces_info
                }, indent=2))]
            except Exception as e:
                return [TextContent(type="text", text=json.dumps({
                    "error": f"Could not determine gateway: {e}",
                    "note": "Full gateway detection requires /proc/net/route (Linux) or the netifaces library"
                }, indent=2))]

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    server = NetConnectionsServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
