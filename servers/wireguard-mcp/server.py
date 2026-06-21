import sys
import json
import os
import subprocess
import re
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


WG = "wg"
WG_DIR = Path("/etc/wireguard")


def _run(args: list[str], timeout: int = 15, input: str | None = None) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, input=input)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or f"exit code {r.returncode}")
        return r.stdout
    except FileNotFoundError:
        raise RuntimeError(f"command not found: {args[0]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"command timed out: {' '.join(args)}")


def _parse_dump(interface: str) -> list[dict[str, Any]]:
    out = _run([WG, "show", interface, "dump"])
    peers = []
    for line in out.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 7:
            peers.append({
                "public_key": parts[0],
                "preshared_key": parts[1],
                "endpoint": parts[2] if parts[2] != "(none)" else None,
                "allowed_ips": parts[3],
                "latest_handshake_secs_ago": int(parts[4]) if parts[4] != "0" else None,
                "transfer_rx": int(parts[5]),
                "transfer_tx": int(parts[6]),
                "persistent_keepalive": parts[7].strip() if len(parts) > 7 else None,
            })
    return peers


class WireguardServer(Server):
    def __init__(self):
        super().__init__("wireguard")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="interface_status",
                description="Show status of a WireGuard interface",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "interface": {"type": "string", "description": "Interface name (e.g. wg0)"}
                    },
                    "required": ["interface"]
                }
            ),
            Tool(
                name="list_interfaces",
                description="List all WireGuard interfaces",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="peer_list",
                description="List all peers on an interface with handshake and transfer info",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "interface": {"type": "string", "description": "Interface name"}
                    },
                    "required": ["interface"]
                }
            ),
            Tool(
                name="peer_info",
                description="Get detailed info for a specific peer on an interface",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "interface": {"type": "string", "description": "Interface name"},
                        "peer_pubkey": {"type": "string", "description": "Peer public key"}
                    },
                    "required": ["interface", "peer_pubkey"]
                }
            ),
            Tool(
                name="generate_keypair",
                description="Generate a new WireGuard private/public keypair",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="generate_preshared",
                description="Generate a WireGuard preshared key",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="interface_config",
                description="Read WireGuard interface config file from /etc/wireguard/",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "interface": {"type": "string", "description": "Interface name"}
                    },
                    "required": ["interface"]
                }
            ),
            Tool(
                name="quick_summary",
                description="Quick status summary of all WireGuard interfaces",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "interface_status":
                iface = args["interface"]
                out = _run([WG, "show", iface])
                return [TextContent(type="text", text=out)]

            elif name == "list_interfaces":
                out = _run([WG, "show", "interfaces"])
                interfaces = out.strip().split() if out.strip() else []
                return [TextContent(type="text", text=json.dumps({"interfaces": interfaces}, indent=2))]

            elif name == "peer_list":
                iface = args["interface"]
                peers = _parse_dump(iface)
                return [TextContent(type="text", text=json.dumps({"interface": iface, "peers": peers}, indent=2))]

            elif name == "peer_info":
                iface = args["interface"]
                pubkey = args["peer_pubkey"]
                peers = _parse_dump(iface)
                match = [p for p in peers if p["public_key"] == pubkey]
                if match:
                    return [TextContent(type="text", text=json.dumps(match[0], indent=2))]
                return [TextContent(type="text", text=json.dumps({"error": f"peer not found on {iface}"}, indent=2))]

            elif name == "generate_keypair":
                priv = _run([WG, "genkey"])
                pub = _run([WG, "pubkey"], timeout=15, input=priv)
                return [TextContent(type="text", text=json.dumps({"private_key": priv.strip(), "public_key": pub.strip()}, indent=2))]

            elif name == "generate_preshared":
                psk = _run([WG, "genpsk"])
                return [TextContent(type="text", text=json.dumps({"preshared_key": psk.strip()}, indent=2))]

            elif name == "interface_config":
                iface = args["interface"]
                cfg = WG_DIR / f"{iface}.conf"
                if cfg.exists():
                    return [TextContent(type="text", text=json.dumps({"interface": iface, "config": cfg.read_text()}, indent=2))]
                return [TextContent(type="text", text=json.dumps({"error": f"config not found: {cfg}"}, indent=2))]

            elif name == "quick_summary":
                out = _run([WG, "show", "interfaces"])
                interfaces = out.strip().split() if out.strip() else []
                summary = []
                for iface in interfaces:
                    try:
                        peers = _parse_dump(iface)
                        peer_count = len(peers)
                        active = sum(1 for p in peers if p["latest_handshake_secs_ago"] is not None and p["latest_handshake_secs_ago"] < 180)
                        total_rx = sum(p["transfer_rx"] for p in peers)
                        total_tx = sum(p["transfer_tx"] for p in peers)
                        summary.append({
                            "interface": iface,
                            "peers": peer_count,
                            "active_peers": active,
                            "total_rx": total_rx,
                            "total_tx": total_tx,
                        })
                    except RuntimeError as e:
                        summary.append({"interface": iface, "error": str(e)})
                return [TextContent(type="text", text=json.dumps({"interfaces": summary}, indent=2))]

            raise ValueError(f"Unknown tool: {name}")
        except RuntimeError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = WireguardServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
