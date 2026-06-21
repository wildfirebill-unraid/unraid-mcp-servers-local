import sys
import json
import os
import pwd
import grp
import subprocess
from pathlib import Path
from typing import Any
from collections import Counter

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class UsersGroupsServer(Server):
    def __init__(self):
        super().__init__("users-groups")

    @staticmethod
    def _parse_passwd() -> list[dict]:
        users = []
        for u in pwd.getpwall():
            users.append({
                "name": u.pw_name,
                "uid": u.pw_uid,
                "gid": u.pw_gid,
                "gecos": u.pw_gecos,
                "home": u.pw_dir,
                "shell": u.pw_shell,
            })
        return users

    @staticmethod
    def _parse_group() -> list[dict]:
        groups = []
        for g in grp.getgrall():
            groups.append({
                "name": g.gr_name,
                "gid": g.gr_gid,
                "members": g.gr_mem,
            })
        return groups

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="list_users",
                description="List all system users from /etc/passwd",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="user_info",
                description="Get detailed info for a specific user",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "description": "Username to query"},
                    },
                    "required": ["username"],
                },
            ),
            Tool(
                name="list_groups",
                description="List all groups from /etc/group",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="group_info",
                description="Get detailed info for a specific group",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "groupname": {"type": "string", "description": "Group name to query"},
                    },
                    "required": ["groupname"],
                },
            ),
            Tool(
                name="user_groups",
                description="List all groups a user belongs to",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "description": "Username"},
                    },
                    "required": ["username"],
                },
            ),
            Tool(
                name="group_members",
                description="List all members of a group",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "groupname": {"type": "string", "description": "Group name"},
                    },
                    "required": ["groupname"],
                },
            ),
            Tool(
                name="logged_in_users",
                description="List currently logged in users",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="recent_logins",
                description="Show recent login history",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer", "description": "Number of entries (default 20)"},
                    },
                },
            ),
            Tool(
                name="process_user_stats",
                description="Count processes per user",
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
        if name == "list_users":
            users = self._parse_passwd()
            return json.dumps(users)

        if name == "user_info":
            username = args.get("username", "")
            try:
                u = pwd.getpwnam(username)
                groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
                return json.dumps({
                    "name": u.pw_name,
                    "uid": u.pw_uid,
                    "gid": u.pw_gid,
                    "gecos": u.pw_gecos,
                    "home": u.pw_dir,
                    "shell": u.pw_shell,
                    "groups": groups,
                })
            except KeyError:
                return json.dumps({"error": f"User '{username}' not found"})

        if name == "list_groups":
            groups = self._parse_group()
            return json.dumps(groups)

        if name == "group_info":
            groupname = args.get("groupname", "")
            try:
                g = grp.getgrnam(groupname)
                return json.dumps({
                    "name": g.gr_name,
                    "gid": g.gr_gid,
                    "members": g.gr_mem,
                })
            except KeyError:
                return json.dumps({"error": f"Group '{groupname}' not found"})

        if name == "user_groups":
            username = args.get("username", "")
            groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
            return json.dumps({"username": username, "groups": groups})

        if name == "group_members":
            groupname = args.get("groupname", "")
            try:
                g = grp.getgrnam(groupname)
                return json.dumps({"group": groupname, "members": g.gr_mem})
            except KeyError:
                return json.dumps({"error": f"Group '{groupname}' not found"})

        if name == "logged_in_users":
            try:
                result = subprocess.run(
                    ["who", "-u"], capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0:
                    return json.dumps({"error": result.stderr.strip()})
                entries = []
                for line in result.stdout.strip().split("\n"):
                    if not line: continue
                    parts = line.split()
                    entries.append({
                        "user": parts[0] if len(parts) > 0 else "",
                        "tty": parts[1] if len(parts) > 1 else "",
                        "time": parts[2] if len(parts) > 2 else "",
                        "from": parts[4] if len(parts) > 4 and parts[3] == "(" else "",
                    })
                return json.dumps(entries)
            except FileNotFoundError:
                return json.dumps({"error": "who command not found"})
            except subprocess.TimeoutExpired:
                return json.dumps({"error": "timed out"})

        if name == "recent_logins":
            count = str(args.get("count", 20))
            try:
                result = subprocess.run(
                    ["last", "-n", count], capture_output=True, text=True, timeout=15
                )
                if result.returncode != 0:
                    return json.dumps({"error": result.stderr.strip()})
                entries = []
                for line in result.stdout.strip().split("\n"):
                    if not line or line.startswith("wtmp") or "reboot" in line.lower():
                        continue
                    parts = line.split()
                    entries.append({
                        "user": parts[0] if len(parts) > 0 else "",
                        "tty": parts[1] if len(parts) > 1 else "",
                        "from": parts[2] if len(parts) > 2 else "",
                        "time": " ".join(parts[3:]) if len(parts) > 3 else "",
                    })
                return json.dumps(entries)
            except FileNotFoundError:
                return json.dumps({"error": "last command not found"})
            except subprocess.TimeoutExpired:
                return json.dumps({"error": "timed out"})

        if name == "process_user_stats":
            try:
                result = subprocess.run(
                    ["ps", "h", "-o", "user"], capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0:
                    return json.dumps({"error": result.stderr.strip()})
                users = [line.strip() for line in result.stdout.split("\n") if line.strip()]
                counts = Counter(users)
                return json.dumps({
                    "total_processes": len(users),
                    "per_user": dict(counts.most_common()),
                })
            except FileNotFoundError:
                return json.dumps({"error": "ps command not found"})
            except subprocess.TimeoutExpired:
                return json.dumps({"error": "timed out"})

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = UsersGroupsServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
