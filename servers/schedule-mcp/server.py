import sys
import json
import os
import subprocess
from pathlib import Path
from typing import Any
from datetime import datetime, timezone, timedelta

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
from croniter import croniter

COMMON_INTERVALS = [
    {"name": "Every minute", "cron": "* * * * *"},
    {"name": "Every 5 minutes", "cron": "*/5 * * * *"},
    {"name": "Every 10 minutes", "cron": "*/10 * * * *"},
    {"name": "Every 15 minutes", "cron": "*/15 * * * *"},
    {"name": "Every 30 minutes", "cron": "*/30 * * * *"},
    {"name": "Every hour", "cron": "0 * * * *"},
    {"name": "Every 2 hours", "cron": "0 */2 * * *"},
    {"name": "Every 3 hours", "cron": "0 */3 * * *"},
    {"name": "Every 6 hours", "cron": "0 */6 * * *"},
    {"name": "Every 12 hours", "cron": "0 */12 * * *"},
    {"name": "Daily at midnight", "cron": "0 0 * * *"},
    {"name": "Daily at 9 AM", "cron": "0 9 * * *"},
    {"name": "Daily at noon", "cron": "0 12 * * *"},
    {"name": "Daily at 6 PM", "cron": "0 18 * * *"},
    {"name": "Every weekday at 9 AM", "cron": "0 9 * * 1-5"},
    {"name": "Every weekday at 5 PM", "cron": "0 17 * * 1-5"},
    {"name": "Weekly on Monday at midnight", "cron": "0 0 * * 1"},
    {"name": "Weekly on Friday at 5 PM", "cron": "0 17 * * 5"},
    {"name": "Monthly on 1st at midnight", "cron": "0 0 1 * *"},
    {"name": "Monthly on 15th at noon", "cron": "0 12 15 * *"},
    {"name": "Quarterly (Jan 1, Apr 1, Jul 1, Oct 1)", "cron": "0 0 1 1,4,7,10 *"},
    {"name": "Yearly on Jan 1st", "cron": "0 0 1 1 *"},
    {"name": "Every Monday", "cron": "0 0 * * 1"},
    {"name": "Every weekend at 8 AM", "cron": "0 8 * * 0,6"},
]

FIELD_NAMES = ["minute", "hour", "day of month", "month", "day of week"]

FIELD_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]


def _parse_cron_field(field: str, field_idx: int) -> dict:
    lo, hi = FIELD_RANGES[field_idx]
    if field == "*":
        return {"type": "every", "description": f"every {FIELD_NAMES[field_idx]}"}
    if field.startswith("*/"):
        step = field[2:]
        return {"type": "every_n", "step": int(step), "description": f"every {step} {FIELD_NAMES[field_idx]}(s)"}
    if "," in field:
        parts = [int(x) for x in field.split(",")]
        vals = sorted(set(p for p in parts if lo <= p <= hi))
        return {"type": "list", "values": vals, "description": f"at {', '.join(str(v) for v in vals)}"}
    if "-" in field:
        parts = field.split("-")
        start, end = int(parts[0]), int(parts[1])
        return {"type": "range", "from": start, "to": end, "description": f"{start}-{end}"}
    val = int(field)
    return {"type": "exact", "value": val, "description": str(val)}


def _describe_cron(expr: str) -> str:
    parts = expr.strip().split()
    if len(parts) != 5:
        return "Invalid cron expression (expected 5 fields)"
    descriptors = []

    min_field = _parse_cron_field(parts[0], 0)
    hr_field = _parse_cron_field(parts[1], 1)
    dom_field = _parse_cron_field(parts[2], 2)
    mon_field = _parse_cron_field(parts[3], 3)
    dow_field = _parse_cron_field(parts[4], 4)

    if parts[2] == "*" and parts[4] == "*":
        if parts[0] == "0" and parts[1] == "*":
            descriptors.append("At the start of every hour")
        elif parts[0] == "0" and hr_field["type"] == "every_n":
            descriptors.append(f"Every {hr_field['step']} hours")
        elif parts[0] != "*" and parts[1] == "*":
            descriptors.append(f"At minute {parts[0]} past every hour")
        elif parts[0] == "*" and parts[1] == "*":
            descriptors.append("Every minute")
        else:
            descriptors.append(f"At {parts[0].zfill(2)}:{parts[1].zfill(2)}")
    else:
        time_str = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        descriptors.append(f"At {time_str}")

    if parts[2] != "*":
        descriptors.append(dom_field["description"])
    if parts[3] != "*":
        descriptors.append(mon_field["description"])
    if parts[4] != "*":
        if parts[4].startswith("*/"):
            step = int(parts[4][2:])
            descriptors.append(f"every {step} days of week")
        elif parts[4] in ("0", "7"):
            descriptors.append("on Sunday")
        elif parts[4] == "1":
            descriptors.append("on Monday")
        elif parts[4] == "2":
            descriptors.append("on Tuesday")
        elif parts[4] == "3":
            descriptors.append("on Wednesday")
        elif parts[4] == "4":
            descriptors.append("on Thursday")
        elif parts[4] == "5":
            descriptors.append("on Friday")
        elif parts[4] == "6":
            descriptors.append("on Saturday")
        elif parts[4] == "1-5":
            descriptors.append("weekdays only")
        elif parts[4] == "0,6" or parts[4] == "0,7" or parts[4] == "6,0":
            descriptors.append("weekends only")
        else:
            descriptors.append(dow_field["description"])

    return ", ".join(descriptors)


class ScheduleServer(Server):
    def __init__(self):
        super().__init__("schedule")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="parse_cron", description="Parse a cron expression into field-level details", inputSchema={"type": "object", "properties": {"expression": {"type": "string", "description": "5-field cron expression"}}, "required": ["expression"]}),
            Tool(name="next_runs", description="Get next N run times for a cron expression", inputSchema={"type": "object", "properties": {"expression": {"type": "string", "description": "5-field cron expression"}, "count": {"type": "integer", "description": "Number of future runs to return (default: 5, max: 100)"}}, "required": ["expression"]}),
            Tool(name="prev_runs", description="Get previous N run times for a cron expression", inputSchema={"type": "object", "properties": {"expression": {"type": "string", "description": "5-field cron expression"}, "count": {"type": "integer", "description": "Number of past runs to return (default: 5, max: 100)"}}, "required": ["expression"]}),
            Tool(name="validate_cron", description="Validate a cron expression string", inputSchema={"type": "object", "properties": {"expression": {"type": "string", "description": "5-field cron expression"}}, "required": ["expression"]}),
            Tool(name="cron_to_human", description="Describe a cron expression in human-readable text", inputSchema={"type": "object", "properties": {"expression": {"type": "string", "description": "5-field cron expression"}}, "required": ["expression"]}),
            Tool(name="list_intervals", description="List common cron intervals (every hour, daily, weekly, etc.)", inputSchema={"type": "object", "properties": {}}),
            Tool(name="time_until_next", description="Seconds until the next scheduled run", inputSchema={"type": "object", "properties": {"expression": {"type": "string", "description": "5-field cron expression"}}, "required": ["expression"]}),
            Tool(name="schedule_description", description="Generate an English description of when a cron schedule runs", inputSchema={"type": "object", "properties": {"expression": {"type": "string", "description": "5-field cron expression"}}, "required": ["expression"]}),
            Tool(name="overlap_analysis", description="Check overlap between two cron schedules over a date range", inputSchema={"type": "object", "properties": {"expr1": {"type": "string", "description": "First cron expression"}, "expr2": {"type": "string", "description": "Second cron expression"}, "from_date": {"type": "string", "description": "Start date (ISO format, e.g. 2026-01-01)"}, "to_date": {"type": "string", "description": "End date (ISO format, e.g. 2026-12-31)"}}, "required": ["expr1", "expr2", "from_date", "to_date"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            now = datetime.now(timezone.utc)

            if name == "parse_cron":
                expr = args.get("expression", "")
                parts = expr.strip().split()
                if len(parts) != 5:
                    raise ValueError("Expected 5 fields in cron expression")
                fields = []
                for i, part in enumerate(parts):
                    fields.append({"field": FIELD_NAMES[i], "raw": part, **{k: v for k, v in _parse_cron_field(part, i).items() if k != "description"}})
                return [TextContent(type="text", text=json.dumps({"expression": expr, "fields": fields}))]

            if name == "next_runs":
                expr = args.get("expression", "")
                count = min(int(args.get("count", 5)), 100)
                if not croniter.is_valid(expr):
                    raise ValueError(f"Invalid cron expression: {expr}")
                cron = croniter(expr, now)
                runs = []
                for _ in range(count):
                    runs.append(cron.get_next(datetime).isoformat())
                return [TextContent(type="text", text=json.dumps({"expression": expr, "from": now.isoformat(), "next_runs": runs}))]

            if name == "prev_runs":
                expr = args.get("expression", "")
                count = min(int(args.get("count", 5)), 100)
                if not croniter.is_valid(expr):
                    raise ValueError(f"Invalid cron expression: {expr}")
                cron = croniter(expr, now)
                runs = []
                for _ in range(count):
                    runs.append(cron.get_prev(datetime).isoformat())
                return [TextContent(type="text", text=json.dumps({"expression": expr, "prev_runs": runs}))]

            if name == "validate_cron":
                expr = args.get("expression", "")
                parts = expr.strip().split()
                valid = croniter.is_valid(expr)
                result = {"expression": expr, "valid": valid}
                if not valid:
                    if len(parts) != 5:
                        result["error"] = f"Expected 5 fields, got {len(parts)}"
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "cron_to_human":
                expr = args.get("expression", "")
                if not croniter.is_valid(expr):
                    raise ValueError(f"Invalid cron expression: {expr}")
                description = _describe_cron(expr)
                return [TextContent(type="text", text=json.dumps({"expression": expr, "description": description}))]

            if name == "list_intervals":
                return [TextContent(type="text", text=json.dumps({"intervals": COMMON_INTERVALS}))]

            if name == "time_until_next":
                expr = args.get("expression", "")
                if not croniter.is_valid(expr):
                    raise ValueError(f"Invalid cron expression: {expr}")
                cron = croniter(expr, now)
                next_run = cron.get_next(datetime)
                seconds = (next_run - now).total_seconds()
                return [TextContent(type="text", text=json.dumps({"expression": expr, "next_run": next_run.isoformat(), "seconds_until_next": int(seconds), "minutes_until_next": round(seconds / 60, 1), "hours_until_next": round(seconds / 3600, 2)}))]

            if name == "schedule_description":
                expr = args.get("expression", "")
                if not croniter.is_valid(expr):
                    raise ValueError(f"Invalid cron expression: {expr}")
                description = _describe_cron(expr)
                cron = croniter(expr, now)
                next_run = cron.get_next(datetime).isoformat()
                return [TextContent(type="text", text=json.dumps({"expression": expr, "description": description, "next_run": next_run}))]

            if name == "overlap_analysis":
                expr1 = args.get("expr1", "")
                expr2 = args.get("expr2", "")
                from_date = args.get("from_date", "")
                to_date = args.get("to_date", "")
                if not croniter.is_valid(expr1):
                    raise ValueError(f"Invalid first expression: {expr1}")
                if not croniter.is_valid(expr2):
                    raise ValueError(f"Invalid second expression: {expr2}")
                dt_start = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
                dt_end = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc)
                runs1 = []
                runs2 = []
                cron1 = croniter(expr1, dt_start)
                cron2 = croniter(expr2, dt_start)
                max_samples = 500
                for _ in range(max_samples):
                    r = cron1.get_next(datetime)
                    if r > dt_end:
                        break
                    runs1.append(r)
                for _ in range(max_samples):
                    r = cron2.get_next(datetime)
                    if r > dt_end:
                        break
                    runs2.append(r)
                set1 = set(r.isoformat() for r in runs1)
                set2 = set(r.isoformat() for r in runs2)
                overlaps = sorted(set1 & set2)
                unique1 = len(set1) - len(overlaps)
                unique2 = len(set2) - len(overlaps)

                result = {"expr1": expr1, "expr2": expr2, "from_date": from_date, "to_date": to_date, "schedule1_runs": len(runs1), "schedule2_runs": len(runs2), "overlapping_runs": len(overlaps), "overlap_times": overlaps[:50] if overlaps else [], "schedule1_unique": unique1, "schedule2_unique": unique2, "truncated": len(overlaps) > 50}
                return [TextContent(type="text", text=json.dumps(result))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = ScheduleServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
