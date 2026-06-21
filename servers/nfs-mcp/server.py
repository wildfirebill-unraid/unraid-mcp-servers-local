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


class NfsServer(Server):
    def __init__(self):
        super().__init__("nfs")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="list_exports", description="List NFS exports from /etc/exports", inputSchema={"type": "object", "properties": {}}),
            Tool(name="show_mounts", description="Show NFS mounts via showmount or /proc/mounts", inputSchema={"type": "object", "properties": {}}),
            Tool(name="mount_stats", description="NFS mount stats from /proc/self/mountstats", inputSchema={"type": "object", "properties": {}}),
            Tool(name="nfs_connections", description="NFS RPC connections via rpcinfo", inputSchema={"type": "object", "properties": {}}),
            Tool(name="export_info", description="Info about a specific NFS export", inputSchema={"type": "object", "properties": {"export_path": {"type": "string", "description": "Export path"}}, "required": ["export_path"]}),
            Tool(name="nfsd_threads", description="NFS server thread count from /proc/net/rpc/nfsd", inputSchema={"type": "object", "properties": {}}),
            Tool(name="nfs_operations", description="NFS operation counters", inputSchema={"type": "object", "properties": {}}),
            Tool(name="active_mounts", description="Active NFS mounts from mount table", inputSchema={"type": "object", "properties": {}}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "list_exports":
            exports = _try_read("/etc/exports")
            return [TextContent(type="text", text=exports)]
        if name == "show_mounts":
            out = _run(["showmount", "-e", "localhost"])
            if "not found" in out:
                mounts = _try_read("/proc/mounts")
                lines = [l for l in mounts.splitlines() if " nfs" in l or " nfs4" in l]
                out = "\n".join(lines) if lines else "(no NFS mounts found)"
            return [TextContent(type="text", text=out)]
        if name == "mount_stats":
            stats = _try_read("/proc/self/mountstats")
            return [TextContent(type="text", text=stats)]
        if name == "nfs_connections":
            out = _run(["rpcinfo", "-p"])
            return [TextContent(type="text", text=out)]
        if name == "export_info":
            path = args.get("export_path", "")
            exports = _try_read("/etc/exports")
            lines = [l for l in exports.splitlines() if path in l]
            return [TextContent(type="text", text="\n".join(lines) if lines else f"No matching export for {path}")]
        if name == "nfsd_threads":
            data = _try_read("/proc/net/rpc/nfsd")
            return [TextContent(type="text", text=data)]
        if name == "nfs_operations":
            data = _try_read("/proc/net/rpc/nfsd")
            return [TextContent(type="text", text=data)]
        if name == "active_mounts":
            mounts = _try_read("/proc/mounts")
            lines = [l for l in mounts.splitlines() if " nfs" in l or " nfs4" in l]
            return [TextContent(type="text", text="\n".join(lines) if lines else "(no active NFS mounts)")]
        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = NfsServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
