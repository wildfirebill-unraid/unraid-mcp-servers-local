import sys
import json
import os
import subprocess
import re
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


IPTABLES = "iptables"
IPTABLES_SAVE = "iptables-save"
IP6TABLES = "ip6tables"
NFT = "nft"


def _run(args: list[str], timeout: int = 15) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or f"exit code {r.returncode}")
        return r.stdout
    except FileNotFoundError:
        raise RuntimeError(f"command not found: {args[0]}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"command timed out: {' '.join(args)}")


def _iptables_list(table: str = "filter", chain: str | None = None) -> str:
    cmd = [IPTABLES, "-t", table, "-L", "--line-numbers", "-n", "-v"]
    if chain:
        cmd.insert(5, chain)
    return _run(cmd)


def _parse_rules(output: str) -> list[dict[str, Any]]:
    rules = []
    current_chain = None
    for line in output.splitlines():
        if line.startswith("Chain "):
            m = re.match(r"Chain\s+(\S+)", line)
            if m:
                current_chain = m.group(1)
                pol = re.search(r"policy\s+(\S+)", line)
                pkts = re.search(r"(\d+)\s+packets", line)
                rules.append({
                    "chain": current_chain,
                    "type": "policy",
                    "policy": pol.group(1) if pol else None,
                    "packets": int(pkts.group(1)) if pkts else 0,
                })
        elif current_chain and re.match(r"^\d+", line):
            parts = line.split()
            if len(parts) >= 8:
                rules.append({
                    "num": int(parts[0]),
                    "pkts": parts[1],
                    "bytes": parts[2],
                    "target": parts[3],
                    "prot": parts[4],
                    "opt": parts[5],
                    "in": parts[6],
                    "out": parts[7],
                    "source": parts[8],
                    "destination": parts[9],
                    "extra": " ".join(parts[10:]) if len(parts) > 10 else "",
                })
    return rules


def _get_tables() -> list[str]:
    tables = ["filter", "nat", "mangle", "raw", "security"]
    available = []
    for t in tables:
        try:
            _run([IPTABLES, "-t", t, "-L", "-n"], timeout=5)
            available.append(t)
        except RuntimeError:
            pass
    return available


def _get_chains(table: str) -> list[str]:
    out = _run([IPTABLES, "-t", table, "-L", "-n"])
    chains = []
    for line in out.splitlines():
        if line.startswith("Chain "):
            m = re.match(r"Chain\s+(\S+)", line)
            if m:
                chains.append(m.group(1))
    return chains


class FirewallServer(Server):
    def __init__(self):
        super().__init__("firewall")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="list_rules",
                description="List iptables rules for a table and chain",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Table name (filter, nat, mangle, raw, security)", "default": "filter"},
                        "chain": {"type": "string", "description": "Chain name (optional, lists all if omitted)"}
                    },
                    "required": []
                }
            ),
            Tool(
                name="list_tables",
                description="List available iptables tables",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="list_chains",
                description="List chains in a specific table",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Table name", "default": "filter"}
                    },
                    "required": []
                }
            ),
            Tool(
                name="rule_count",
                description="Count rules in a table and chain",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Table name", "default": "filter"},
                        "chain": {"type": "string", "description": "Chain name", "default": "INPUT"}
                    },
                    "required": []
                }
            ),
            Tool(
                name="table_summary",
                description="Brief summary of all tables, chains, and rule counts",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="check_port",
                description="Check if a port is allowed by current firewall rules",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "port": {"type": "integer", "description": "Port number"},
                        "protocol": {"type": "string", "description": "Protocol (tcp/udp)", "default": "tcp"}
                    },
                    "required": ["port"]
                }
            ),
            Tool(
                name="connection_tracking",
                description="Show current connection tracking count",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="list_nat_rules",
                description="List NAT table rules",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "list_rules":
                table = args.get("table", "filter")
                chain = args.get("chain")
                out = _iptables_list(table, chain)
                return [TextContent(type="text", text=out)]

            elif name == "list_tables":
                tables = _get_tables()
                return [TextContent(type="text", text=json.dumps({"tables": tables}, indent=2))]

            elif name == "list_chains":
                table = args.get("table", "filter")
                chains = _get_chains(table)
                return [TextContent(type="text", text=json.dumps({"table": table, "chains": chains}, indent=2))]

            elif name == "rule_count":
                table = args.get("table", "filter")
                chain = args.get("chain", "INPUT")
                out = _iptables_list(table, chain)
                rules = _parse_rules(out)
                count = sum(1 for r in rules if r["type"] != "policy")
                return [TextContent(type="text", text=json.dumps({"table": table, "chain": chain, "rule_count": count}, indent=2))]

            elif name == "table_summary":
                tables = _get_tables()
                summary = []
                for t in tables:
                    chains = _get_chains(t)
                    chain_info = []
                    for c in chains:
                        try:
                            out = _iptables_list(t, c)
                            rules = _parse_rules(out)
                            rule_count = sum(1 for r in rules if r["type"] != "policy")
                            policy = next((r["policy"] for r in rules if r["type"] == "policy"), None)
                            chain_info.append({"chain": c, "policy": policy, "rules": rule_count})
                        except RuntimeError:
                            chain_info.append({"chain": c, "error": "unable to read"})
                    summary.append({"table": t, "chains": chain_info})
                return [TextContent(type="text", text=json.dumps({"tables": summary}, indent=2))]

            elif name == "check_port":
                port = args["port"]
                protocol = args.get("protocol", "tcp")
                out = _run([IPTABLES, "-L", "INPUT", "-n", "-v"])
                allowed = False
                for line in out.splitlines():
                    if re.search(rf"\b{protocol}\b.*\b{port}\b", line, re.IGNORECASE) and "DROP" not in line:
                        allowed = True
                        break
                return [TextContent(type="text", text=json.dumps({
                    "port": port,
                    "protocol": protocol,
                    "allowed": allowed,
                }, indent=2))]

            elif name == "connection_tracking":
                try:
                    conntrack_path = Path("/proc/sys/net/netfilter/nf_conntrack_count")
                    if conntrack_path.exists():
                        count = int(conntrack_path.read_text().strip())
                        return [TextContent(type="text", text=json.dumps({"connection_count": count}, indent=2))]
                    out = _run(["conntrack", "-C"], timeout=5)
                    return [TextContent(type="text", text=json.dumps({"connection_count": int(out.strip())}, indent=2))]
                except (RuntimeError, ValueError, FileNotFoundError):
                    return [TextContent(type="text", text=json.dumps({"error": "connection tracking not available"}, indent=2))]

            elif name == "list_nat_rules":
                out = _iptables_list("nat")
                return [TextContent(type="text", text=out)]

            raise ValueError(f"Unknown tool: {name}")
        except RuntimeError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = FirewallServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
