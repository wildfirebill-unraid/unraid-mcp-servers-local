import sys
import json
import subprocess
import re
from pathlib import Path
from typing import Any
from datetime import datetime, timedelta

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


def _dpkg_query(*args: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            ["dpkg-query"] + list(args),
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return json.dumps({"error": result.stderr.strip() or "dpkg-query failed"})
        return result.stdout
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "dpkg-query timed out"})
    except FileNotFoundError:
        return json.dumps({"error": "dpkg-query not found — is this a Debian-based system?"})


class PackagesServer(Server):
    def __init__(self):
        super().__init__("packages")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="list_packages",
                description="List installed packages, optionally filtered",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filter_str": {"type": "string", "description": "Filter package names containing this string"},
                    },
                },
            ),
            Tool(
                name="package_info",
                description="Get detailed information about a specific package",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "package_name": {"type": "string", "description": "Package name"},
                    },
                    "required": ["package_name"],
                },
            ),
            Tool(
                name="search_packages",
                description="Search packages by name or description",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search term"},
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="package_files",
                description="List all files owned by a package",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "package_name": {"type": "string", "description": "Package name"},
                    },
                    "required": ["package_name"],
                },
            ),
            Tool(
                name="package_dependencies",
                description="List dependencies of a package",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "package_name": {"type": "string", "description": "Package name"},
                    },
                    "required": ["package_name"],
                },
            ),
            Tool(
                name="package_size",
                description="Get installed size of a package",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "package_name": {"type": "string", "description": "Package name"},
                    },
                    "required": ["package_name"],
                },
            ),
            Tool(
                name="orphaned_packages",
                description="List orphaned/auto-removable packages",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="recent_installs",
                description="List recently installed packages from dpkg log",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "hours": {"type": "integer", "description": "Lookback hours (default 24)"},
                    },
                },
            ),
            Tool(
                name="package_count",
                description="Total number of installed packages",
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
        if name == "list_packages":
            filter_str = args.get("filter_str", "")
            raw = _dpkg_query("-W", "--showformat=${Package}\t${Version}\t${Installed-Size}\t${Status}\n")
            if raw.startswith("{"):
                return raw
            packages = []
            for line in raw.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) >= 4:
                    pkg = {"name": parts[0], "version": parts[1], "size_kb": parts[2], "status": parts[3]}
                    if not filter_str or filter_str.lower() in pkg["name"].lower():
                        packages.append(pkg)
            return json.dumps(packages)

        if name == "package_info":
            pkg = args.get("package_name", "")
            if not pkg:
                return json.dumps({"error": "package_name is required"})
            fields = [
                ("Package", "name"),
                ("Version", "version"),
                ("Architecture", "architecture"),
                ("Installed-Size", "size_kb"),
                ("Maintainer", "maintainer"),
                ("Description", "description"),
                ("Homepage", "homepage"),
                ("Section", "section"),
                ("Priority", "priority"),
                ("Depends", "depends"),
                ("Pre-Depends", "pre_depends"),
                ("Recommends", "recommends"),
                ("Suggests", "suggests"),
                ("Status", "status"),
                ("Source", "source"),
            ]
            showformat = "\t".join(f"${{{f[0]}}}" for f in fields)
            raw = _dpkg_query("-W", "--showformat", showformat + "\n", pkg)
            if raw.startswith("{"):
                return raw
            parts = raw.strip().split("\t")
            info = {}
            for i, f in enumerate(fields):
                info[f[1]] = parts[i] if i < len(parts) else ""
            return json.dumps(info)

        if name == "search_packages":
            query = args.get("query", "")
            if not query:
                return json.dumps({"error": "query is required"})
            raw = _dpkg_query("-W", "--showformat=${Package}\t${Description}\n", "*" + query + "*")
            if raw.startswith("{"):
                raw2 = _dpkg_query("-W", "--showformat=${Package}\t${Description}\n")
                if raw2.startswith("{"):
                    return raw2
                results = []
                for line in raw2.strip().split("\n"):
                    parts = line.split("\t", 1)
                    if len(parts) == 2 and (query.lower() in parts[0].lower() or query.lower() in parts[1].lower()):
                        results.append({"name": parts[0], "description": parts[1]})
                return json.dumps(results)
            results = []
            for line in raw.strip().split("\n"):
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    results.append({"name": parts[0], "description": parts[1]})
            return json.dumps(results)

        if name == "package_files":
            pkg = args.get("package_name", "")
            if not pkg:
                return json.dumps({"error": "package_name is required"})
            try:
                result = subprocess.run(
                    ["dpkg", "-L", pkg],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    return json.dumps({"error": result.stderr.strip()})
                files = [line for line in result.stdout.strip().split("\n") if line]
                return json.dumps({"package": pkg, "files": files})
            except FileNotFoundError:
                return json.dumps({"error": "dpkg not found"})

        if name == "package_dependencies":
            pkg = args.get("package_name", "")
            if not pkg:
                return json.dumps({"error": "package_name is required"})
            raw = _dpkg_query("-W", "-f", "${Depends}\n", pkg)
            if raw.startswith("{"):
                return raw
            deps = [d.strip() for d in raw.strip().split(",") if d.strip()]
            return json.dumps({"package": pkg, "dependencies": deps})

        if name == "package_size":
            pkg = args.get("package_name", "")
            if not pkg:
                return json.dumps({"error": "package_name is required"})
            raw = _dpkg_query("-W", "-f", "${Installed-Size}\n", pkg)
            if raw.startswith("{"):
                return raw
            try:
                kb = int(raw.strip())
                return json.dumps({"package": pkg, "size_kb": kb, "size_mb": round(kb / 1024, 2)})
            except ValueError:
                return json.dumps({"error": f"Could not parse size for '{pkg}'"})

        if name == "orphaned_packages":
            try:
                result = subprocess.run(
                    ["apt-get", "--just-print", "autoremove"],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    return json.dumps({"error": result.stderr.strip()})
                matches = re.findall(r'Remv\s+(\S+)', result.stdout)
                return json.dumps({"orphaned_packages": matches, "count": len(matches)})
            except FileNotFoundError:
                return json.dumps({"error": "apt-get not found"})

        if name == "recent_installs":
            hours = args.get("hours", 24)
            cutoff = datetime.now() - timedelta(hours=hours)
            log_path = Path("/var/log/dpkg.log")
            if not log_path.exists():
                return json.dumps({"error": "dpkg log not found at /var/log/dpkg.log"})
            recent = []
            for line in log_path.read_text().split("\n"):
                if not line: continue
                try:
                    ts_str = line[:19]
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    if ts >= cutoff and " install " in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            recent.append({"time": ts_str, "package": parts[3]})
                except ValueError:
                    continue
            return json.dumps({"period_hours": hours, "installs": recent, "count": len(recent)})

        if name == "package_count":
            raw = _dpkg_query("-W", "--showformat=${Package}\n")
            if raw.startswith("{"):
                return raw
            count = len([l for l in raw.strip().split("\n") if l])
            return json.dumps({"installed_packages": count})

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = PackagesServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
