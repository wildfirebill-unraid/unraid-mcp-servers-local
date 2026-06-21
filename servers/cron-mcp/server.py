import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("cron-mcp")

BASE_PATH = Path(os.environ.get("CRON_MCP_PATH", "/data"))

WEEKDAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
MONTH_NAMES = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

def _expand_field(field: str, min_val: int, max_val: int) -> list[int]:
    if field == "*":
        return list(range(min_val, max_val + 1))
    values = set()
    parts = field.split(",")
    for part in parts:
        if "/" in part:
            base, step = part.split("/")
            step = int(step)
            if base == "*":
                rng = range(min_val, max_val + 1)
            elif "-" in base:
                a, b = base.split("-")
                rng = range(int(a), int(b) + 1)
            else:
                rng = range(int(base), max_val + 1)
            values.update(rng[::step])
        elif "-" in part:
            a, b = part.split("-")
            values.update(range(int(a), int(b) + 1))
        else:
            values.add(int(part))
    return sorted(v for v in values if min_val <= v <= max_val)

def _parse_cron_expression(expression: str) -> dict:
    parts = expression.strip().split()
    if len(parts) < 5:
        return {"valid": False, "error": "Cron expression must have at least 5 fields"}
    minute, hour, dom, month, dow = parts[:5]
    try:
        return {
            "valid": True,
            "minute": minute,
            "hour": hour,
            "day_of_month": dom,
            "month": month,
            "day_of_week": dow,
            "expanded": {
                "minutes": _expand_field(minute, 0, 59),
                "hours": _expand_field(hour, 0, 23),
                "days_of_month": _expand_field(dom, 1, 31),
                "months": _expand_field(month, 1, 12),
                "days_of_week": _expand_field(dow, 0, 6),
            },
        }
    except (ValueError, IndexError) as e:
        return {"valid": False, "error": str(e)}

def _cron_to_human(expression: str) -> str:
    parts = expression.strip().split()
    if len(parts) < 5:
        return "Invalid cron expression"
    minute, hour, dom, month, dow = parts[:5]

    def desc(field, singular, plural):
        if field == "*":
            return f"every {plural}"
        if "/" in field:
            base, step = field.split("/")
            if base == "*":
                return f"every {step} {plural}"
            return f"every {step} {plural} starting at {base}"
        if "," in field:
            return f"at {field} {plural}"
        if "-" in field:
            return f"from {field} {plural}"
        return f"at {field}"

    parts_desc = []
    if minute != "*":
        parts_desc.append(desc(minute, "minute", "minutes"))
    if hour != "*":
        parts_desc.append(desc(hour, "hour", "hours"))
    if dom != "*":
        parts_desc.append(f"on day {dom} of month")
    if month != "*":
        parts_desc.append(f"in month {month}")
    if dow != "*":
        parts_desc.append(f"on {dow} day of week")

    if minute == "*" and hour == "*" and dom == "*" and month == "*" and dow == "*":
        return "Every minute"

    return "Runs " + ", ".join(parts_desc)

def _next_runs(expression: str, count: int = 5) -> list[str]:
    parsed = _parse_cron_expression(expression)
    if not parsed["valid"]:
        return [f"Error: {parsed.get('error')}"]
    expanded = parsed["expanded"]
    now = datetime.now().replace(second=0, microsecond=0)
    runs = []
    current = now
    while len(runs) < count:
        current += timedelta(minutes=1)
        if current.month in expanded["months"] and \
           current.day in expanded["days_of_month"] and \
           current.hour in expanded["hours"] and \
           current.minute in expanded["minutes"]:
            runs.append(current.isoformat())
    return runs

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="parse_cron",
            description="Parse a cron expression and describe when it runs",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Cron expression like '*/5 * * * * /script.sh'"}
                },
                "required": ["expression"],
            },
        ),
        Tool(
            name="next_runs",
            description="Calculate next N run times for a cron expression",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Cron expression"},
                    "count": {"type": "integer", "description": "Number of runs to calculate", "default": 5},
                },
                "required": ["expression"],
            },
        ),
        Tool(
            name="list_crontab",
            description="List current user's crontab entries",
            inputSchema={
                "type": "object",
                "properties": {
                    "user": {"type": "string", "description": "Optional username"}
                },
            },
        ),
        Tool(
            name="validate_cron",
            description="Validate a cron expression",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Cron expression"}
                },
                "required": ["expression"],
            },
        ),
        Tool(
            name="cron_schedule_summary",
            description="Give human summary of what the cron does",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Cron expression"}
                },
                "required": ["expression"],
            },
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "parse_cron":
        expr = arguments["expression"]
        parsed = _parse_cron_expression(expr)
        result = json.dumps(parsed, indent=2)

    elif name == "next_runs":
        expr = arguments["expression"]
        count = arguments.get("count", 5)
        runs = _next_runs(expr, count)
        result = json.dumps(runs, indent=2)

    elif name == "list_crontab":
        import subprocess
        user = arguments.get("user")
        cmd = ["crontab", "-l"]
        if user:
            cmd = ["crontab", "-u", user, "-l"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            result = r.stdout or r.stderr or "No crontab"
        except FileNotFoundError:
            result = "Error: crontab command not found"
        except subprocess.TimeoutExpired:
            result = "Error: command timed out"

    elif name == "validate_cron":
        expr = arguments["expression"]
        parsed = _parse_cron_expression(expr)
        result = json.dumps({"valid": parsed["valid"], "error": parsed.get("error")}, indent=2)

    elif name == "cron_schedule_summary":
        expr = arguments["expression"]
        summary = _cron_to_human(expr)
        result = json.dumps({"expression": expr, "summary": summary}, indent=2)

    else:
        result = f"Unknown tool: {name}"

    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="cron-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
