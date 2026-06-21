import sys
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Any
from collections import Counter
from datetime import datetime, timedelta

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


def _run_journalctl(*args: str, timeout: int = 30) -> str:
    cmd = ["journalctl", "--no-pager", "-o", "json"] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return json.dumps({"error": result.stderr.strip() or "journalctl failed"})
        lines = [l for l in result.stdout.split("\n") if l.strip()]
        return "[" + ",".join(lines) + "]" if lines else "[]"
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "journalctl timed out"})
    except FileNotFoundError:
        return json.dumps({"error": "journalctl not found — is systemd journal available?"})


def _run_journalctl_cat(*args: str, timeout: int = 30) -> str:
    cmd = ["journalctl", "--no-pager", "-o", "cat"] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return json.dumps({"error": result.stderr.strip() or "journalctl failed"})
        return result.stdout
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "journalctl timed out"})
    except FileNotFoundError:
        return json.dumps({"error": "journalctl not found"})


class JournaldServer(Server):
    def __init__(self):
        super().__init__("journald")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="query_journal",
                description="Query systemd journal with filters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "since": {"type": "string", "description": "Start time (e.g. 'yesterday', '1 hour ago', '2024-01-01 00:00:00')"},
                        "until": {"type": "string", "description": "End time"},
                        "priority": {"type": "string", "description": "Priority filter: emerg,alert,crit,err,warning,info,debug"},
                        "unit": {"type": "string", "description": "Systemd unit name (e.g. 'sshd', 'nginx')"},
                        "lines": {"type": "integer", "description": "Number of recent lines"},
                    },
                },
            ),
            Tool(
                name="follow_journal",
                description="Get latest journal entries (like journalctl -n)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lines": {"type": "integer", "description": "Number of entries (default 50)"},
                        "unit": {"type": "string", "description": "Filter by unit"},
                    },
                },
            ),
            Tool(
                name="boot_history",
                description="List boot history via journalctl --list-boots",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="unit_logs",
                description="Get logs for a specific systemd unit",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "unit": {"type": "string", "description": "Unit name (e.g. sshd.service)"},
                        "lines": {"type": "integer", "description": "Number of lines"},
                        "since": {"type": "string", "description": "Start time"},
                    },
                    "required": ["unit"],
                },
            ),
            Tool(
                name="priority_logs",
                description="Filter journal by priority level",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "priority": {"type": "string", "description": "Priority: emerg,alert,crit,err,warning,info,debug"},
                        "since": {"type": "string", "description": "Start time"},
                        "lines": {"type": "integer", "description": "Number of lines"},
                    },
                    "required": ["priority"],
                },
            ),
            Tool(
                name="journal_stats",
                description="Journal disk usage statistics",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="time_range_logs",
                description="Get journal logs within a specific time range",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "since": {"type": "string", "description": "Start time (required)"},
                        "until": {"type": "string", "description": "End time"},
                        "lines": {"type": "integer", "description": "Number of lines"},
                    },
                    "required": ["since"],
                },
            ),
            Tool(
                name="query_by_field",
                description="Query journal by a specific field (e.g. _PID=123)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "description": "Field query like '_PID=123' or 'SYSLOG_IDENTIFIER=sshd'"},
                        "value": {"type": "string", "description": "Field value (alternative to combined field param)"},
                        "lines": {"type": "integer", "description": "Number of lines"},
                    },
                    "required": ["field"],
                },
            ),
            Tool(
                name="log_summary",
                description="Summary of log levels grouped by hour",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "since": {"type": "string", "description": "Start time (default '24 hours ago')"},
                        "hours": {"type": "integer", "description": "Lookback hours (default 24)"},
                    },
                },
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
        if name == "query_journal":
            cmd = []
            since = args.get("since")
            until = args.get("until")
            priority = args.get("priority")
            unit = args.get("unit")
            lines = args.get("lines")
            if since: cmd += ["--since", since]
            if until: cmd += ["--until", until]
            if priority: cmd += ["-p", priority]
            if unit: cmd += ["-u", unit]
            if lines: cmd += ["-n", str(lines)]
            return _run_journalctl(*cmd)

        if name == "follow_journal":
            cmd = ["-n", str(args.get("lines", 50))]
            if args.get("unit"): cmd += ["-u", args["unit"]]
            return _run_journalctl(*cmd)

        if name == "boot_history":
            try:
                result = subprocess.run(
                    ["journalctl", "--list-boots", "--no-pager"],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode != 0:
                    return json.dumps({"error": result.stderr.strip()})
                entries = []
                for line in result.stdout.strip().split("\n"):
                    parts = line.split()
                    if len(parts) >= 3:
                        entries.append({"idx": parts[0], "boot_id": parts[1], "time": " ".join(parts[2:])})
                return json.dumps(entries)
            except subprocess.TimeoutExpired:
                return json.dumps({"error": "timed out"})
            except FileNotFoundError:
                return json.dumps({"error": "journalctl not found"})

        if name == "unit_logs":
            unit = args.get("unit")
            if not unit:
                return json.dumps({"error": "unit is required"})
            cmd = ["-u", unit, "-n", str(args.get("lines", 100))]
            if args.get("since"): cmd += ["--since", args["since"]]
            return _run_journalctl(*cmd)

        if name == "priority_logs":
            p = args.get("priority", "err")
            cmd = ["-p", p, "-n", str(args.get("lines", 100))]
            if args.get("since"): cmd += ["--since", args["since"]]
            return _run_journalctl(*cmd)

        if name == "journal_stats":
            try:
                result = subprocess.run(
                    ["journalctl", "--disk-usage"],
                    capture_output=True, text=True, timeout=15,
                )
                return json.dumps({"output": result.stdout.strip(), "error": result.stderr.strip() or None})
            except subprocess.TimeoutExpired:
                return json.dumps({"error": "timed out"})
            except FileNotFoundError:
                return json.dumps({"error": "journalctl not found"})

        if name == "time_range_logs":
            since = args.get("since")
            if not since:
                return json.dumps({"error": "since is required"})
            cmd = ["--since", since, "-n", str(args.get("lines", 100))]
            if args.get("until"): cmd += ["--until", args["until"]]
            return _run_journalctl(*cmd)

        if name == "query_by_field":
            field = args.get("field", "")
            val = args.get("value")
            if val:
                field = f"{field}={val}" if "=" not in field else field
            lines = str(args.get("lines", 50))
            return _run_journalctl(field, "-n", lines)

        if name == "log_summary":
            hours = args.get("hours", 24)
            since = args.get("since", f"{hours} hours ago")
            raw = _run_journalctl_cat("--since", since, "-p", "debug")
            if raw.startswith("{"):
                return raw
            levels = Counter()
            for line in raw.split("\n"):
                l = line.strip().lower()
                if not l: continue
                if "emerg" in l or "panic" in l: levels["emerg"] += 1
                elif "alert" in l: levels["alert"] += 1
                elif "crit" in l or "critical" in l: levels["crit"] += 1
                elif "err" in l and "error" not in l: levels["err"] += 1
                elif "error" in l: levels["error"] += 1
                elif "warn" in l or "warning" in l: levels["warning"] += 1
                elif "info" in l: levels["info"] += 1
                elif "debug" in l: levels["debug"] += 1
                else: levels["unknown"] += 1
            return json.dumps({
                "period_hours": hours,
                "since": since,
                "total_lines": len(raw.split("\n")),
                "summary": dict(levels.most_common()),
            })

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = JournaldServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
