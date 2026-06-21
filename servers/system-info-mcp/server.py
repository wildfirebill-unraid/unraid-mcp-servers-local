import os
import time
import shutil
import socket
import platform
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("system-info-mcp")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

@server.list_tools()
async def list_tools() -> list[Tool]:
    tools = [
        Tool(
            name="get_system_info",
            description="Get basic system information (hostname, OS, architecture, uptime)",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_cpu_info",
            description="Get CPU usage, cores, frequency, and load average",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_memory_info",
            description="Get RAM usage statistics (total, available, used, percent)",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_disk_info",
            description="Get disk partition usage (mount, total, used, free, percent)",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_network_info",
            description="Get network interface statistics (bytes sent/recv, packets)",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_process_list",
            description="Get list of running processes sorted by CPU usage",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max processes to return (default 20)"}
                },
                "required": []
            }
        ),
        Tool(
            name="get_uptime",
            description="Get system uptime in human-readable format",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_disk_io",
            description="Get disk I/O statistics",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
    ]
    return tools

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = ""

    if name == "get_system_info":
        boot_time = ""
        if HAS_PSUTIL:
            boot_time = time.ctime(psutil.boot_time())
        result = str({
            "hostname": socket.gethostname(),
            "os": platform.system(),
            "os_version": platform.release(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "boot_time": boot_time,
            "python_version": platform.python_version(),
        })

    elif name == "get_cpu_info":
        if not HAS_PSUTIL:
            return [TextContent(type="text", text="psutil not available")]
        result = str({
            "physical_cores": psutil.cpu_count(logical=False),
            "total_cores": psutil.cpu_count(logical=True),
            "max_frequency_mhz": psutil.cpu_freq().max if psutil.cpu_freq() else "N/A",
            "current_frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else "N/A",
            "cpu_percent_per_core": psutil.cpu_percent(percpu=True),
            "total_cpu_percent": psutil.cpu_percent(),
            "load_avg": [round(x, 2) for x in os.getloadavg()] if hasattr(os, "getloadavg") else "N/A",
        })

    elif name == "get_memory_info":
        if not HAS_PSUTIL:
            return [TextContent(type="text", text="psutil not available")]
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        result = str({
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "percent": mem.percent,
            "swap_total_gb": round(swap.total / (1024**3), 2),
            "swap_used_gb": round(swap.used / (1024**3), 2),
            "swap_percent": swap.percent,
        })

    elif name == "get_disk_info":
        if not HAS_PSUTIL:
            return [TextContent(type="text", text="psutil not available")]
        partitions = []
        for p in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(p.mountpoint)
                partitions.append({
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent": usage.percent,
                })
            except PermissionError:
                pass
        result = str(partitions)

    elif name == "get_network_info":
        if not HAS_PSUTIL:
            return [TextContent(type="text", text="psutil not available")]
        net = psutil.net_io_counters()
        interfaces = {}
        for iface, stats in psutil.net_if_stats().items():
            if iface == "lo":
                continue
            io = psutil.net_io_counters(pernic=True).get(iface)
            interfaces[iface] = {
                "is_up": stats.isup,
                "speed_mbps": stats.speed,
                "bytes_sent": io.bytes_sent if io else 0,
                "bytes_recv": io.bytes_recv if io else 0,
            }
        result = str({
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
            "interfaces": interfaces,
        })

    elif name == "get_process_list":
        if not HAS_PSUTIL:
            return [TextContent(type="text", text="psutil not available")]
        limit = arguments.get("limit", 20)
        processes = []
        for proc in sorted(psutil.process_iter(attrs=["pid", "name", "cpu_percent", "memory_percent"]),
                          key=lambda p: p.info.get("cpu_percent", 0) or 0, reverse=True)[:limit]:
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        result = str(processes)

    elif name == "get_uptime":
        if not HAS_PSUTIL:
            return [TextContent(type="text", text="psutil not available")]
        uptime_sec = time.time() - psutil.boot_time()
        days = int(uptime_sec // 86400)
        hours = int((uptime_sec % 86400) // 3600)
        minutes = int((uptime_sec % 3600) // 60)
        result = f"{days}d {hours}h {minutes}m"

    elif name == "get_disk_io":
        if not HAS_PSUTIL:
            return [TextContent(type="text", text="psutil not available")]
        io = psutil.disk_io_counters()
        result = str({
            "read_count": io.read_count,
            "write_count": io.write_count,
            "read_bytes_gb": round(io.read_bytes / (1024**3), 2),
            "write_bytes_gb": round(io.write_bytes / (1024**3), 2),
            "read_time_ms": io.read_time,
            "write_time_ms": io.write_time,
        })

    else:
        raise ValueError(f"Unknown tool: {name}")

    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="system-info-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
