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


RAID_INFO = {
    "0": "RAID 0 (striping): data split across disks, no redundancy, N disks = Nx performance.",
    "1": "RAID 1 (mirroring): identical data on all disks, N-way mirror, read performance scales.",
    "5": "RAID 5 (striped parity): single parity distributed across disks, tolerates 1 disk failure.",
    "6": "RAID 6 (dual parity): two parity stripes, tolerates 2 disk failures.",
    "10": "RAID 10 (striped mirrors): nested RAID 1+0, performance and redundancy combined.",
}


class MdadmServer(Server):
    def __init__(self):
        super().__init__("mdadm")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="list_arrays", description="List MD arrays from /proc/mdstat", inputSchema={"type": "object", "properties": {}}),
            Tool(name="array_detail", description="Detailed info about an MD array", inputSchema={"type": "object", "properties": {"device": {"type": "string", "description": "Array device (e.g. md0, md127)"}}, "required": ["device"]}),
            Tool(name="array_status", description="Status of all arrays from /proc/mdstat", inputSchema={"type": "object", "properties": {}}),
            Tool(name="component_info", description="Component disks of an MD array", inputSchema={"type": "object", "properties": {"device": {"type": "string", "description": "Array device (e.g. md0)"}}, "required": ["device"]}),
            Tool(name="spare_disks", description="List spare disks in MD arrays", inputSchema={"type": "object", "properties": {}}),
            Tool(name="scan_arrays", description="Scan all MD arrays via mdadm --detail --scan", inputSchema={"type": "object", "properties": {}}),
            Tool(name="raid_level_info", description="Description of a RAID level", inputSchema={"type": "object", "properties": {"level": {"type": "string", "description": "RAID level (0, 1, 5, 6, 10)"}}, "required": ["level"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "list_arrays":
            data = _try_read("/proc/mdstat")
            return [TextContent(type="text", text=data)]
        if name == "array_detail":
            dev = args.get("device", "")
            out = _run(["mdadm", "--detail", f"/dev/{dev.removeprefix('/dev/')}"])
            return [TextContent(type="text", text=out)]
        if name == "array_status":
            data = _try_read("/proc/mdstat")
            return [TextContent(type="text", text=data)]
        if name == "component_info":
            dev = args.get("device", "")
            out = _run(["mdadm", "--detail", f"/dev/{dev.removeprefix('/dev/')}"])
            return [TextContent(type="text", text=out)]
        if name == "spare_disks":
            data = _try_read("/proc/mdstat")
            spare_lines = [l for l in data.splitlines() if "spare" in l.lower()]
            if not spare_lines:
                detail = _run(["mdadm", "--detail", "--scan"])
                spare_lines = [detail] if detail else ["(no spare disks found)"]
            return [TextContent(type="text", text="\n".join(spare_lines) if spare_lines else "(no spare disks)")]
        if name == "scan_arrays":
            out = _run(["mdadm", "--detail", "--scan"])
            return [TextContent(type="text", text=out)]
        if name == "raid_level_info":
            level = args.get("level", "")
            desc = RAID_INFO.get(level, f"No description for RAID level {level}")
            return [TextContent(type="text", text=desc)]
        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = MdadmServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
