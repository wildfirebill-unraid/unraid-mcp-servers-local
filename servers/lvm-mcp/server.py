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


def _get_vgs() -> list[str]:
    r = _run(["vgs", "--noheadings", "-o", "vg_name"])
    return [x.strip() for x in r.splitlines() if x.strip() and not x.startswith("Error") and not x.startswith("Command")]


class LvmServer(Server):
    def __init__(self):
        super().__init__("lvm")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="pv_list", description="List physical volumes", inputSchema={"type": "object", "properties": {}}),
            Tool(name="pv_detail", description="Detailed PV info", inputSchema={"type": "object", "properties": {"pv_name": {"type": "string", "description": "PV device path (e.g. /dev/sda1)"}}, "required": ["pv_name"]}),
            Tool(name="vg_list", description="List volume groups", inputSchema={"type": "object", "properties": {}}),
            Tool(name="vg_detail", description="Detailed VG info", inputSchema={"type": "object", "properties": {"vg_name": {"type": "string", "description": "Volume group name"}}, "required": ["vg_name"]}),
            Tool(name="lv_list", description="List logical volumes, optionally filtered by VG", inputSchema={"type": "object", "properties": {"vg_name": {"type": "string", "description": "Volume group name (optional)"}}}),
            Tool(name="lv_detail", description="Detailed LV info", inputSchema={"type": "object", "properties": {"lv_path": {"type": "string", "description": "LV path (e.g. /dev/vg0/lvol0)"}}, "required": ["lv_path"]}),
            Tool(name="pvs_by_vg", description="List PVs belonging to a VG", inputSchema={"type": "object", "properties": {"vg_name": {"type": "string", "description": "Volume group name"}}, "required": ["vg_name"]}),
            Tool(name="lvm_version", description="LVM version info", inputSchema={"type": "object", "properties": {}}),
            Tool(name="volume_tree", description="Hierarchical view PVs -> VGs -> LVs", inputSchema={"type": "object", "properties": {}}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "pv_list":
            out = _run(["pvs"])
            return [TextContent(type="text", text=out)]
        if name == "pv_detail":
            pv = args.get("pv_name", "")
            out = _run(["pvdisplay", pv])
            return [TextContent(type="text", text=out)]
        if name == "vg_list":
            out = _run(["vgs"])
            return [TextContent(type="text", text=out)]
        if name == "vg_detail":
            vg = args.get("vg_name", "")
            out = _run(["vgdisplay", vg])
            return [TextContent(type="text", text=out)]
        if name == "lv_list":
            vg = args.get("vg_name", "")
            if vg:
                out = _run(["lvs", vg])
            else:
                out = _run(["lvs"])
            return [TextContent(type="text", text=out)]
        if name == "lv_detail":
            lv = args.get("lv_path", "")
            out = _run(["lvdisplay", lv])
            return [TextContent(type="text", text=out)]
        if name == "pvs_by_vg":
            vg = args.get("vg_name", "")
            out = _run(["pvs", "--noheadings", "-o", "pv_name,vg_name", "--select", f"vg_name={vg}"])
            return [TextContent(type="text", text=out if not out.startswith("Command") else _run(["pvdisplay"]) + f"\n(fallback: could not filter by VG {vg})")]
        if name == "lvm_version":
            ver = _run(["lvm", "version"])
            return [TextContent(type="text", text=ver)]
        if name == "volume_tree":
            vgs = _get_vgs()
            parts = []
            for vg in vgs:
                pv_out = _run(["pvs", "--noheadings", "-o", "pv_name,pv_size", "--select", f"vg_name={vg}"])
                lv_out = _run(["lvs", "--noheadings", "-o", "lv_name,lv_size", vg])
                parts.append(f"VG: {vg}")
                for line in pv_out.splitlines():
                    parts.append(f"  PV  {line.strip()}")
                for line in lv_out.splitlines():
                    parts.append(f"  LV  {line.strip()}")
                parts.append("")
            return [TextContent(type="text", text="\n".join(parts) if parts else "(no volume groups found)")]
        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = LvmServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
