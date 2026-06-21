import os
import json
import signal
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio
import psutil

server = Server("process-mcp")

def get_process_info(p: psutil.Process) -> dict:
    with p.oneshot():
        try:
            return {
                "pid": p.pid,
                "name": p.name(),
                "status": p.status(),
                "cpu_percent": p.cpu_percent(interval=0),
                "memory_percent": p.memory_percent(),
                "memory_rss": p.memory_info().rss,
                "create_time": p.create_time(),
                "cmdline": " ".join(p.cmdline()) if p.cmdline() else "",
                "username": p.username(),
                "num_threads": p.num_threads(),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_processes",
            description="List processes with optional filtering and sorting",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {"type": "string", "description": "Filter by process name"},
                    "sort_by": {"type": "string", "description": "Sort field (cpu/memory/pid/name)", "default": "pid"},
                    "limit": {"type": "integer", "description": "Max results", "default": 50}
                }
            }
        ),
        Tool(
            name="kill_process",
            description="Kill a process by PID",
            inputSchema={
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "Process ID"},
                    "signal": {"type": "string", "description": "Signal to send (SIGTERM/SIGKILL/SIGINT)", "default": "SIGTERM"}
                },
                "required": ["pid"]
            }
        ),
        Tool(
            name="process_tree",
            description="Show process tree for a PID",
            inputSchema={
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "Process ID"}
                },
                "required": ["pid"]
            }
        ),
        Tool(
            name="find_process",
            description="Search for processes by name or command",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query matching name or command line"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="process_stats",
            description="Get detailed stats for a specific PID",
            inputSchema={
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "Process ID"}
                },
                "required": ["pid"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "list_processes":
        name_filter = arguments.get("filter", "").lower()
        sort_by = arguments.get("sort_by", "pid")
        limit = arguments.get("limit", 50)
        processes = []
        for p in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_percent", "memory_info", "create_time", "cmdline", "username", "num_threads"]):
            info = get_process_info(p)
            if info is None:
                continue
            if name_filter and name_filter not in info["name"].lower():
                continue
            processes.append(info)
        sort_map = {
            "cpu": lambda x: x.get("cpu_percent", 0),
            "memory": lambda x: x.get("memory_percent", 0),
            "pid": lambda x: x.get("pid", 0),
            "name": lambda x: x.get("name", ""),
        }
        key_fn = sort_map.get(sort_by, sort_map["pid"])
        processes.sort(key=key_fn, reverse=(sort_by in ("cpu", "memory")))
        processes = processes[:limit]
        return [TextContent(type="text", text=json.dumps(processes, indent=2, default=str))]
    elif name == "kill_process":
        pid = arguments["pid"]
        sig_name = arguments.get("signal", "SIGTERM")
        sig_map = {"SIGTERM": signal.SIGTERM, "SIGKILL": signal.SIGKILL, "SIGINT": signal.SIGINT}
        sig = sig_map.get(sig_name, signal.SIGTERM)
        try:
            p = psutil.Process(pid)
            p.send_signal(sig)
            return [TextContent(type="text", text=json.dumps({"status": "ok", "pid": pid, "signal": sig_name}))]
        except psutil.NoSuchProcess:
            return [TextContent(type="text", text=json.dumps({"status": "error", "message": f"Process {pid} not found"}))]
        except psutil.AccessDenied:
            return [TextContent(type="text", text=json.dumps({"status": "error", "message": f"Access denied to process {pid}"}))]
    elif name == "process_tree":
        pid = arguments["pid"]
        try:
            parent = psutil.Process(pid)
            tree = {"pid": parent.pid, "name": parent.name(), "status": parent.status()}
            children = parent.children(recursive=True)
            tree["children"] = [{"pid": c.pid, "name": c.name(), "status": c.status()} for c in children if c.is_running()]
            return [TextContent(type="text", text=json.dumps(tree, indent=2))]
        except psutil.NoSuchProcess:
            return [TextContent(type="text", text=json.dumps({"error": f"Process {pid} not found"}))]
    elif name == "find_process":
        query = arguments["query"].lower()
        results = []
        for p in psutil.process_iter(["pid", "name", "cmdline", "status"]):
            try:
                pinfo = p.info
                name = (pinfo["name"] or "").lower()
                cmdline = " ".join(pinfo["cmdline"] or []).lower()
                if query in name or query in cmdline:
                    results.append({
                        "pid": pinfo["pid"],
                        "name": pinfo["name"],
                        "status": pinfo["status"],
                        "cmdline": " ".join(pinfo["cmdline"] or [])
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return [TextContent(type="text", text=json.dumps(results, indent=2))]
    elif name == "process_stats":
        pid = arguments["pid"]
        try:
            p = psutil.Process(pid)
            with p.oneshot():
                info = {
                    "pid": p.pid,
                    "name": p.name(),
                    "exe": p.exe(),
                    "status": p.status(),
                    "create_time": p.create_time(),
                    "cmdline": " ".join(p.cmdline()) if p.cmdline() else "",
                    "username": p.username(),
                    "cpu_percent": p.cpu_percent(interval=0.1),
                    "cpu_times": p.cpu_times(),
                    "memory_percent": p.memory_percent(),
                    "memory_info": p.memory_info(),
                    "num_threads": p.num_threads(),
                    "num_fds": p.num_fds() if hasattr(p, 'num_fds') else None,
                    "connections": len(p.connections()),
                    "open_files": len(p.open_files()),
                }
            return [TextContent(type="text", text=json.dumps(info, indent=2, default=str))]
        except psutil.NoSuchProcess:
            return [TextContent(type="text", text=json.dumps({"error": f"Process {pid} not found"}))]
        except psutil.AccessDenied:
            return [TextContent(type="text", text=json.dumps({"error": f"Access denied to process {pid}"}))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="process-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
