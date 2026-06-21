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


def _run(cmd: list[str], timeout: int = 30) -> str:
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


class ZfsServer(Server):
    def __init__(self):
        super().__init__("zfs")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="list_pools", description="List ZFS pools", inputSchema={"type": "object", "properties": {}}),
            Tool(name="pool_detail", description="Detailed info about a ZFS pool", inputSchema={"type": "object", "properties": {"pool_name": {"type": "string", "description": "Pool name"}}, "required": ["pool_name"]}),
            Tool(name="list_datasets", description="List datasets in a pool", inputSchema={"type": "object", "properties": {"pool": {"type": "string", "description": "Pool name"}}, "required": ["pool"]}),
            Tool(name="dataset_info", description="Dataset properties", inputSchema={"type": "object", "properties": {"dataset": {"type": "string", "description": "Dataset name"}}, "required": ["dataset"]}),
            Tool(name="pool_health", description="Health status of all pools", inputSchema={"type": "object", "properties": {}}),
            Tool(name="pool_capacity", description="Capacity info for a pool", inputSchema={"type": "object", "properties": {"pool_name": {"type": "string", "description": "Pool name"}}, "required": ["pool_name"]}),
            Tool(name="snapshot_list", description="List snapshots for a dataset", inputSchema={"type": "object", "properties": {"dataset": {"type": "string", "description": "Dataset name"}}, "required": ["dataset"]}),
            Tool(name="zfs_version", description="ZFS version info", inputSchema={"type": "object", "properties": {}}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "list_pools":
            out = _run(["zpool", "list"])
            return [TextContent(type="text", text=out)]
        if name == "pool_detail":
            pool = args.get("pool_name", "")
            out = _run(["zpool", "status", pool])
            return [TextContent(type="text", text=out)]
        if name == "list_datasets":
            pool = args.get("pool", "")
            out = _run(["zfs", "list", "-r", pool])
            return [TextContent(type="text", text=out)]
        if name == "dataset_info":
            ds = args.get("dataset", "")
            out = _run(["zfs", "get", "all", ds])
            return [TextContent(type="text", text=out)]
        if name == "pool_health":
            out = _run(["zpool", "status", "-x"])
            return [TextContent(type="text", text=out)]
        if name == "pool_capacity":
            pool = args.get("pool_name", "")
            out = _run(["zpool", "list", pool])
            return [TextContent(type="text", text=out)]
        if name == "snapshot_list":
            ds = args.get("dataset", "")
            out = _run(["zfs", "list", "-t", "snapshot", "-r", ds])
            return [TextContent(type="text", text=out)]
        if name == "zfs_version":
            ver = _run(["zpool", "version"])
            mod = "Not available"
            try:
                mod = Path("/sys/module/zfs/version").read_text().strip()
            except Exception:
                pass
            return [TextContent(type="text", text=f"zpool version:\n{ver}\n\nmodule version:\n{mod}")]
        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = ZfsServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
