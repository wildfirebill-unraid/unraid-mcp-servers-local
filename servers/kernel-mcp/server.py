import sys
import json
import os
import subprocess
import platform
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


def _proc_read(path: str) -> str:
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        return ""
    except PermissionError:
        return json.dumps({"error": f"Permission denied reading {path}"})


def _proc_parse_keyval(text: str) -> dict:
    data = {}
    for line in text.strip().split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            data[k.strip()] = v.strip()
    return data


class KernelServer(Server):
    def __init__(self):
        super().__init__("kernel")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="kernel_info",
                description="Get kernel version, release, architecture, hostname",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="cpu_info",
                description="Get CPU information from /proc/cpuinfo",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="memory_info",
                description="Get memory information from /proc/meminfo",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="load_average",
                description="Get system load average",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="uptime_info",
                description="Get system uptime",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="module_list",
                description="List loaded kernel modules",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filter": {"type": "string", "description": "Filter modules by name"},
                    },
                },
            ),
            Tool(
                name="module_info",
                description="Get detailed info about a kernel module",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "module_name": {"type": "string", "description": "Module name"},
                    },
                    "required": ["module_name"],
                },
            ),
            Tool(
                name="sysctl_get",
                description="Read a kernel sysctl parameter",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Sysctl key (e.g. kernel.hostname)"},
                    },
                    "required": ["key"],
                },
            ),
            Tool(
                name="interrupts_info",
                description="Get interrupt statistics from /proc/interrupts",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="devices_info",
                description="Get device info from /proc/devices",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            data = await self._handle(name, args)
            return [TextContent(type="text", text=data)]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def _handle(self, name: str, args: dict) -> str:
        if name == "kernel_info":
            uname = platform.uname()
            return json.dumps({
                "system": uname.system,
                "node": uname.node,
                "release": uname.release,
                "version": uname.version,
                "machine": uname.machine,
                "processor": uname.processor,
            })

        if name == "cpu_info":
            text = _proc_read("/proc/cpuinfo")
            if not text:
                return json.dumps({"error": "Cannot read /proc/cpuinfo"})
            cpus = []
            current = {}
            for line in text.strip().split("\n"):
                if not line:
                    if current: cpus.append(current)
                    current = {}
                    continue
                if ":" in line:
                    k, _, v = line.partition(":")
                    current[k.strip()] = v.strip()
            if current: cpus.append(current)

            summary = {}
            if cpus:
                summary["count"] = len(cpus)
                if "model name" in cpus[0]:
                    summary["model"] = cpus[0]["model name"]
                if "cpu MHz" in cpus[0]:
                    summary["mhz"] = cpus[0]["cpu MHz"]
                if "cache size" in cpus[0]:
                    summary["cache"] = cpus[0]["cache size"]
                if "flags" in cpus[0]:
                    summary["flags"] = cpus[0]["flags"]
            summary["details"] = cpus
            return json.dumps(summary)

        if name == "memory_info":
            text = _proc_read("/proc/meminfo")
            if not text:
                return json.dumps({"error": "Cannot read /proc/meminfo"})
            data = _proc_parse_keyval(text)
            result = {}
            for k, v in data.items():
                parts = v.split()
                num = None
                try:
                    num = int(parts[0]) if parts else None
                except (ValueError, IndexError):
                    pass
                result[k] = {"raw": v}
                if num is not None:
                    result[k]["kb"] = num
                    if len(parts) > 1:
                        result[k]["unit"] = parts[1]
                    mb = round(num / 1024, 1)
                    gb = round(num / 1024 / 1024, 2)
                    result[k]["mb"] = mb
                    result[k]["gb"] = gb
            return json.dumps(result)

        if name == "load_average":
            text = _proc_read("/proc/loadavg")
            if not text:
                return json.dumps({"error": "Cannot read /proc/loadavg"})
            parts = text.strip().split()
            load = {"1min": parts[0], "5min": parts[1], "15min": parts[2]}
            if len(parts) >= 4:
                procs = parts[3].split("/")
                load["running"] = procs[0]
                load["total"] = procs[1] if len(procs) > 1 else ""
            if len(parts) >= 5:
                load["last_pid"] = parts[4]
            return json.dumps(load)

        if name == "uptime_info":
            text = _proc_read("/proc/uptime")
            if not text:
                return json.dumps({"error": "Cannot read /proc/uptime"})
            parts = text.strip().split()
            uptime_secs = float(parts[0])
            idle_secs = float(parts[1]) if len(parts) > 1 else 0
            days = int(uptime_secs // 86400)
            hours = int((uptime_secs % 86400) // 3600)
            minutes = int((uptime_secs % 3600) // 60)
            return json.dumps({
                "uptime_seconds": uptime_secs,
                "idle_seconds": idle_secs,
                "uptime_human": f"{days}d {hours}h {minutes}m",
                "days": days,
                "hours": hours,
                "minutes": minutes,
            })

        if name == "module_list":
            text = _proc_read("/proc/modules")
            if not text:
                return json.dumps({"error": "Cannot read /proc/modules"})
            filter_str = args.get("filter", "")
            modules = []
            for line in text.strip().split("\n"):
                if not line: continue
                parts = line.split()
                mod = {"name": parts[0], "size": parts[1], "instances": parts[2], "depends": parts[3].strip(",") if len(parts) > 3 else ""}
                if not filter_str or filter_str.lower() in mod["name"].lower():
                    modules.append(mod)
            return json.dumps(modules)

        if name == "module_info":
            mod_name = args.get("module_name", "")
            if not mod_name:
                return json.dumps({"error": "module_name is required"})
            text = _proc_read("/proc/modules")
            if not text:
                return json.dumps({"error": "Cannot read /proc/modules"})
            for line in text.strip().split("\n"):
                parts = line.split()
                if parts and parts[0] == mod_name:
                    info = {
                        "name": parts[0],
                        "size_bytes": parts[1],
                        "instances": parts[2],
                        "depends": parts[3].strip(",") if len(parts) > 3 else "",
                        "state": parts[4] if len(parts) > 4 else "",
                        "offset": parts[5] if len(parts) > 5 else "",
                    }
                    if os.path.exists(f"/sys/module/{mod_name}/parameters"):
                        info["has_parameters"] = True
                    return json.dumps(info)
            return json.dumps({"error": f"Module '{mod_name}' not found"})

        if name == "sysctl_get":
            key = args.get("key", "")
            if not key:
                return json.dumps({"error": "key is required"})
            try:
                result = subprocess.run(
                    ["sysctl", "-n", key],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode != 0:
                    return json.dumps({"error": result.stderr.strip() or f"Failed to read {key}"})
                return json.dumps({"key": key, "value": result.stdout.strip()})
            except FileNotFoundError:
                return json.dumps({"error": "sysctl not found"})

        if name == "interrupts_info":
            text = _proc_read("/proc/interrupts")
            if not text:
                return json.dumps({"error": "Cannot read /proc/interrupts"})
            lines = text.strip().split("\n")
            if not lines:
                return json.dumps({"error": "Empty /proc/interrupts"})
            headers = lines[0].split()
            irqs = []
            for line in lines[1:]:
                if not line: continue
                parts = line.split()
                irq = {"irq": parts[0].rstrip(":")}
                cpu_counts = {}
                for i, h in enumerate(headers):
                    if i + 1 < len(parts):
                        cpu_counts[h] = parts[i + 1]
                    elif i + 1 >= len(parts):
                        break
                irq["cpu_counts"] = cpu_counts
                desc_idx = len(headers) + 1
                if desc_idx < len(parts):
                    irq["description"] = " ".join(parts[desc_idx:])
                irqs.append(irq)
            return json.dumps(irqs)

        if name == "devices_info":
            text = _proc_read("/proc/devices")
            if not text:
                return json.dumps({"error": "Cannot read /proc/devices"})
            char_devices = []
            block_devices = []
            current = None
            for line in text.strip().split("\n"):
                if line.startswith("Character devices:"):
                    current = "char"
                    continue
                if line.startswith("Block devices:"):
                    current = "block"
                    continue
                if not line: continue
                parts = line.split()
                if len(parts) >= 2:
                    dev = {"major": parts[0], "name": parts[1]}
                    if current == "char":
                        char_devices.append(dev)
                    else:
                        block_devices.append(dev)
            return json.dumps({"character": char_devices, "block": block_devices})

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = KernelServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
