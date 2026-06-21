import sys
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


def _try_read(path: str) -> str:
    try:
        return Path(path).read_text()
    except Exception as e:
        return f"Error reading {path}: {e}"


def _run(cmd: list[str], timeout: int = 15) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            return f"Command {' '.join(cmd)} failed (exit {r.returncode}): {r.stderr.strip()}"
        return r.stdout.strip() or "(empty output)"
    except FileNotFoundError:
        return f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return f"Command timed out: {' '.join(cmd)}"
    except Exception as e:
        return f"Error running {' '.join(cmd)}: {e}"


def _parse_smbconf(path: str = "/etc/samba/smb.conf") -> dict:
    result = {}
    try:
        current_section = None
        for line in Path(path).read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1]
                result[current_section] = []
            elif current_section and "=" in stripped:
                k, _, v = stripped.partition("=")
                result[current_section].append(f"{k.strip()} = {v.strip()}")
        return result
    except Exception:
        return {"error": f"Could not read {path}"}


class SambaServer(Server):
    def __init__(self):
        super().__init__("samba")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="list_shares", description="List Samba shares from smbstatus or smb.conf", inputSchema={"type": "object", "properties": {}}),
            Tool(name="share_info", description="Info about a specific Samba share", inputSchema={"type": "object", "properties": {"share_name": {"type": "string", "description": "Share name"}}, "required": ["share_name"]}),
            Tool(name="active_connections", description="Active SMB connections via smbstatus", inputSchema={"type": "object", "properties": {}}),
            Tool(name="locked_files", description="Locked files via smbstatus -L", inputSchema={"type": "object", "properties": {}}),
            Tool(name="samba_config", description="Read Samba configuration sections from smb.conf", inputSchema={"type": "object", "properties": {}}),
            Tool(name="samba_stats", description="Samba daemon status", inputSchema={"type": "object", "properties": {}}),
            Tool(name="browse_network", description="Browse SMB network via nmblookup", inputSchema={"type": "object", "properties": {}}),
            Tool(name="client_connections", description="Connections from a specific client", inputSchema={"type": "object", "properties": {"client_ip": {"type": "string", "description": "Client IP address"}}, "required": ["client_ip"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "list_shares":
            out = _run(["smbstatus", "-S"])
            if "not found" in out or "failed" in out:
                config = _parse_smbconf()
                shares = [s for s in config if s.lower() != "global" and s != "error"]
                out = json.dumps(shares, indent=2) if shares else "(no shares found in smb.conf)"
            return [TextContent(type="text", text=out)]
        if name == "share_info":
            share = args.get("share_name", "")
            out = _run(["smbstatus", "-S"])
            lines = [l for l in out.splitlines() if share.lower() in l.lower()]
            if not lines:
                config = _parse_smbconf()
                if share in config:
                    out = f"[{share}]\n" + "\n".join(config[share])
                else:
                    out = f"No share found: {share}"
            else:
                out = "\n".join(lines)
            return [TextContent(type="text", text=out)]
        if name == "active_connections":
            out = _run(["smbstatus"])
            return [TextContent(type="text", text=out)]
        if name == "locked_files":
            out = _run(["smbstatus", "-L"])
            return [TextContent(type="text", text=out)]
        if name == "samba_config":
            config = _parse_smbconf()
            parts = [f"[{s}]\n" + "\n".join(config[s]) for s in config if s != "error"]
            return [TextContent(type="text", text="\n\n".join(parts) if parts else json.dumps(config, indent=2))]
        if name == "samba_stats":
            out = _run(["smbstatus"])
            return [TextContent(type="text", text=out)]
        if name == "browse_network":
            out = _run(["nmblookup", "-S", "__SAMBA__"], timeout=10)
            return [TextContent(type="text", text=out)]
        if name == "client_connections":
            ip = args.get("client_ip", "")
            out = _run(["smbstatus"])
            lines = [l for l in out.splitlines() if ip in l]
            return [TextContent(type="text", text="\n".join(lines) if lines else f"No connections from {ip}")]
        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = SambaServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
