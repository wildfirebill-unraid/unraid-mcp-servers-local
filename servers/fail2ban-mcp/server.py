import sys
import json
import os
import subprocess
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


F2B_CLIENT = "fail2ban-client"
F2B_LOG = "/var/log/fail2ban.log"


def _run(args: list[str], timeout: int = 30) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or f"exit code {r.returncode}")
        return r.stdout
    except FileNotFoundError:
        raise RuntimeError(f"command not found: {args[0]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"command timed out after {timeout}s: {' '.join(args)}")


def _parse_jail_status(jail: str) -> dict[str, Any]:
    out = _run([F2B_CLIENT, "status", jail])
    result = {"jail": jail, "status": {}, "banned_ips": []}
    for line in out.splitlines():
        line = line.strip()
        if "Status for the jail:" in line:
            result["jail"] = line.split(":")[-1].strip()
        elif "|-" in line or "`-" in line:
            parts = re.split(r"\s*\|\s*", line, maxsplit=1)
            if len(parts) == 2:
                k = parts[0].strip("- ").strip("`- ").strip()
                v = parts[1].strip()
                result["status"][k] = v
        elif "Banned IP list:" in line:
            ip_part = line.split("Banned IP list:")[-1].strip()
            if ip_part:
                result["banned_ips"] = [ip.strip() for ip in ip_part.split() if ip.strip()]
    return result


class Fail2banServer(Server):
    def __init__(self):
        super().__init__("fail2ban")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="jail_status",
                description="Get detailed status of a specific fail2ban jail",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "jail_name": {"type": "string", "description": "Jail name"}
                    },
                    "required": ["jail_name"]
                }
            ),
            Tool(
                name="list_jails",
                description="List all active fail2ban jails",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="banned_ips",
                description="List currently banned IPs for a jail",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "jail_name": {"type": "string", "description": "Jail name"}
                    },
                    "required": ["jail_name"]
                }
            ),
            Tool(
                name="ban_count",
                description="Get total ban count for a jail",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "jail_name": {"type": "string", "description": "Jail name"}
                    },
                    "required": ["jail_name"]
                }
            ),
            Tool(
                name="recent_offenses",
                description="Scan fail2ban log for recent ban events",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "hours": {"type": "integer", "description": "Hours to look back", "default": 24}
                    },
                    "required": []
                }
            ),
            Tool(
                name="unban_ip",
                description="Unban an IP address from a jail",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "jail_name": {"type": "string", "description": "Jail name"},
                        "ip": {"type": "string", "description": "IP address to unban"}
                    },
                    "required": ["jail_name", "ip"]
                }
            ),
            Tool(
                name="jail_config",
                description="Read fail2ban jail configuration from disk",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "jail_name": {"type": "string", "description": "Jail name"}
                    },
                    "required": ["jail_name"]
                }
            ),
            Tool(
                name="overall_status",
                description="Get summary of all jails",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "jail_status":
                jail = args["jail_name"]
                data = _parse_jail_status(jail)
                return [TextContent(type="text", text=json.dumps(data, indent=2))]

            elif name == "list_jails":
                out = _run([F2B_CLIENT, "status"])
                jails = []
                for line in out.splitlines():
                    m = re.search(r"Jail list:\s*(.+)", line)
                    if m:
                        jails = [j.strip() for j in m.group(1).split(",") if j.strip()]
                return [TextContent(type="text", text=json.dumps({"jails": jails}, indent=2))]

            elif name == "banned_ips":
                jail = args["jail_name"]
                data = _parse_jail_status(jail)
                return [TextContent(type="text", text=json.dumps({"jail": jail, "banned_ips": data["banned_ips"]}, indent=2))]

            elif name == "ban_count":
                jail = args["jail_name"]
                data = _parse_jail_status(jail)
                count = data["status"].get("Currently banned", 0)
                total = data["status"].get("Total banned", 0)
                return [TextContent(type="text", text=json.dumps({"jail": jail, "currently_banned": int(count), "total_banned": int(total)}, indent=2))]

            elif name == "recent_offenses":
                hours = int(args.get("hours", 24))
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                log_path = Path(F2B_LOG)
                if not log_path.exists():
                    return [TextContent(type="text", text=json.dumps({"error": f"log not found: {F2B_LOG}"}, indent=2))]
                offenses = []
                for line in log_path.read_text(errors="replace").splitlines():
                    m = re.match(r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?\](.*?)(?:Ban|Found)\s+(\S+)", line)
                    if m:
                        ts_str = m.group(1)
                        try:
                            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                            if ts >= cutoff:
                                offenses.append({"timestamp": ts_str, "message": line.strip()})
                        except ValueError:
                            continue
                return [TextContent(type="text", text=json.dumps({"hours": hours, "offenses": offenses[-200:]}, indent=2))]

            elif name == "unban_ip":
                jail = args["jail_name"]
                ip = args["ip"]
                try:
                    out = _run([F2B_CLIENT, "set", jail, "unbanip", ip])
                    return [TextContent(type="text", text=json.dumps({"jail": jail, "ip": ip, "result": out.strip()}, indent=2))]
                except RuntimeError as e:
                    s = str(e)
                    if "NOT" in s and "banned" in s:
                        return [TextContent(type="text", text=json.dumps({"jail": jail, "ip": ip, "result": "IP not currently banned"}, indent=2))]
                    raise

            elif name == "jail_config":
                jail = args["jail_name"]
                paths = [
                    Path(f"/etc/fail2ban/jail.local"),
                    Path(f"/etc/fail2ban/jail.d/{jail}.conf"),
                    Path(f"/etc/fail2ban/jail.d/{jail}.local"),
                    Path(f"/etc/fail2ban/jail.conf"),
                ]
                for p in paths:
                    if p.exists():
                        content = p.read_text()
                        jail_section = re.search(rf"\[{jail}\](.*?)(?=\n\[|\Z)", content, re.DOTALL)
                        if jail_section:
                            return [TextContent(type="text", text=json.dumps({"jail": jail, "source": str(p), "config": jail_section.group(0).strip()}, indent=2))]
                return [TextContent(type="text", text=json.dumps({"error": f"config not found for jail: {jail}"}, indent=2))]

            elif name == "overall_status":
                jails_out = _run([F2B_CLIENT, "status"])
                jails = []
                for line in jails_out.splitlines():
                    m = re.search(r"Jail list:\s*(.+)", line)
                    if m:
                        jails = [j.strip() for j in m.group(1).split(",") if j.strip()]
                summaries = []
                for j in jails:
                    try:
                        data = _parse_jail_status(j)
                        summaries.append({
                            "jail": j,
                            "currently_banned": int(data["status"].get("Currently banned", 0)),
                            "total_banned": int(data["status"].get("Total banned", 0)),
                            "failed": int(data["status"].get("Total failed", 0)),
                            "ip_count": len(data["banned_ips"])
                        })
                    except RuntimeError:
                        summaries.append({"jail": j, "error": "could not read status"})
                return [TextContent(type="text", text=json.dumps({"jails": summaries}, indent=2))]

            raise ValueError(f"Unknown tool: {name}")
        except RuntimeError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = Fail2banServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
