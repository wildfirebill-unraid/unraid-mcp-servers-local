import json
import ipaddress
import random

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

class CidrServer(Server):
    def __init__(self):
        super().__init__("cidr")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="subnet_info", description="Get detailed information about a CIDR subnet",
                 inputSchema={"type":"object","properties":{"cidr":{"type":"string","description":"CIDR notation (e.g. 192.168.1.0/24)"}},"required":["cidr"]}),
            Tool(name="divide_subnet", description="Divide a subnet into smaller subnets with a given prefix",
                 inputSchema={"type":"object","properties":{"cidr":{"type":"string","description":"CIDR notation to divide"},"prefix":{"type":"integer","description":"New prefix length for subnets"}},"required":["cidr","prefix"]}),
            Tool(name="supernet", description="Find common supernet for a list of CIDRs",
                 inputSchema={"type":"object","properties":{"cidrs":{"type":"array","items":{"type":"string"},"description":"List of CIDR notations"}},"required":["cidrs"]}),
            Tool(name="list_hosts", description="List all usable host IPs in a subnet",
                 inputSchema={"type":"object","properties":{"cidr":{"type":"string","description":"CIDR notation"}},"required":["cidr"]}),
            Tool(name="random_ip", description="Pick a random usable IP from a subnet",
                 inputSchema={"type":"object","properties":{"cidr":{"type":"string","description":"CIDR notation"}},"required":["cidr"]}),
            Tool(name="cidr_diff", description="Show difference between two CIDRs",
                 inputSchema={"type":"object","properties":{"cidr1":{"type":"string","description":"First CIDR"},"cidr2":{"type":"string","description":"Second CIDR"}},"required":["cidr1","cidr2"]}),
            Tool(name="cidr_merge", description="Merge adjacent subnets into the smallest list",
                 inputSchema={"type":"object","properties":{"cidrs":{"type":"array","items":{"type":"string"},"description":"List of CIDR notations"}},"required":["cidrs"]}),
            Tool(name="usable_range", description="Get first/last usable IP and count",
                 inputSchema={"type":"object","properties":{"cidr":{"type":"string","description":"CIDR notation"}},"required":["cidr"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        try:
            args = arguments or {}
            if name == "subnet_info":
                net = ipaddress.ip_network(args["cidr"], strict=False)
                return [TextContent(type="text", text=json.dumps({
                    "network_address": str(net.network_address),
                    "netmask": str(net.netmask),
                    "broadcast_address": str(net.broadcast_address) if net.broadcast_address else None,
                    "prefix_length": net.prefixlen,
                    "num_hosts": net.num_addresses - 2 if net.num_addresses > 2 else net.num_addresses,
                    "is_private": net.is_private,
                    "is_global": net.is_global,
                }, indent=2))]

            if name == "divide_subnet":
                net = ipaddress.ip_network(args["cidr"], strict=False)
                new_prefix = int(args["prefix"])
                subnets = list(net.subnets(new_prefix=new_prefix))
                return [TextContent(type="text", text=json.dumps({
                    "count": len(subnets),
                    "subnets": [str(s) for s in subnets],
                }, indent=2))]

            if name == "supernet":
                nets = [ipaddress.ip_network(c, strict=False) for c in args["cidrs"]]
                summary = ipaddress.collapse_addresses(nets)
                supernets = list(ipaddress.collapse_addresses(nets))
                return [TextContent(type="text", text=json.dumps({
                    "supernet": str(supernets[0]) if len(supernets) == 1 else [str(s) for s in supernets],
                    "count": len(supernets),
                }, indent=2))]

            if name == "list_hosts":
                net = ipaddress.ip_network(args["cidr"], strict=False)
                hosts = [str(h) for h in net.hosts()]
                return [TextContent(type="text", text=json.dumps({
                    "count": len(hosts),
                    "hosts": hosts,
                }, indent=2))]

            if name == "random_ip":
                net = ipaddress.ip_network(args["cidr"], strict=False)
                hosts = list(net.hosts())
                if not hosts:
                    return [TextContent(type="text", text=json.dumps({"error": "No usable hosts in this subnet"}))]
                chosen = str(random.choice(hosts))
                return [TextContent(type="text", text=json.dumps({"random_ip": chosen}, indent=2))]

            if name == "cidr_diff":
                net1 = ipaddress.ip_network(args["cidr1"], strict=False)
                net2 = ipaddress.ip_network(args["cidr2"], strict=False)
                in1_not2 = [str(h) for h in net1.hosts() if h not in net2]
                in2_not1 = [str(h) for h in net2.hosts() if h not in net1]
                return [TextContent(type="text", text=json.dumps({
                    "in_first_not_second": in1_not2,
                    "in_second_not_first": in2_not1,
                    "first_hosts": net1.num_addresses,
                    "second_hosts": net2.num_addresses,
                }, indent=2))]

            if name == "cidr_merge":
                nets = [ipaddress.ip_network(c, strict=False) for c in args["cidrs"]]
                merged = list(ipaddress.collapse_addresses(nets))
                return [TextContent(type="text", text=json.dumps({
                    "original_count": len(nets),
                    "merged_count": len(merged),
                    "merged": [str(m) for m in merged],
                }, indent=2))]

            if name == "usable_range":
                net = ipaddress.ip_network(args["cidr"], strict=False)
                hosts = list(net.hosts())
                if not hosts:
                    return [TextContent(type="text", text=json.dumps({
                        "first_usable": None,
                        "last_usable": None,
                        "count": 0
                    }, indent=2))]
                return [TextContent(type="text", text=json.dumps({
                    "first_usable": str(hosts[0]),
                    "last_usable": str(hosts[-1]),
                    "count": len(hosts),
                }, indent=2))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    server = CidrServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
