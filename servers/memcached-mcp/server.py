import json
import os

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
from pymemcache.client.base import Client


class MemcachedServer(Server):
    def __init__(self):
        super().__init__("memcached")
        self._init_env()

    def _init_env(self):
        host = os.environ.get("MEMCACHED_HOST", "localhost")
        port = int(os.environ.get("MEMCACHED_PORT", "11211"))
        self._client = Client((host, port))

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="get_value", description="Get value by key", inputSchema={"type": "object", "properties": {"key": {"type": "string", "description": "Key"}}, "required": ["key"]}),
            Tool(name="set_value", description="Set a key with optional TTL", inputSchema={"type": "object", "properties": {"key": {"type": "string", "description": "Key"}, "value": {"type": "string", "description": "Value"}, "ttl": {"type": "number", "description": "TTL in seconds (optional)"}}, "required": ["key", "value"]}),
            Tool(name="delete_key", description="Delete a key", inputSchema={"type": "object", "properties": {"key": {"type": "string", "description": "Key"}}, "required": ["key"]}),
            Tool(name="flush_all", description="Flush all data", inputSchema={"type": "object", "properties": {}}),
            Tool(name="server_stats", description="Server statistics", inputSchema={"type": "object", "properties": {}}),
            Tool(name="get_multi", description="Get multiple keys", inputSchema={"type": "object", "properties": {"keys": {"type": "string", "description": "Comma-separated keys"}}, "required": ["keys"]}),
            Tool(name="set_multi", description="Set multiple keys", inputSchema={"type": "object", "properties": {"items_json": {"type": "string", "description": "JSON object of key:value pairs"}}, "required": ["items_json"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "get_value":
                key = args["key"]
                val = self._client.get(key)
                return [TextContent(type="text", text=json.dumps({"key": key, "value": val.decode() if val else None}))]
            elif name == "set_value":
                key = args["key"]
                value = args["value"]
                ttl = args.get("ttl", 0)
                self._client.set(key, value, expire=ttl)
                return [TextContent(type="text", text=json.dumps({"status": "set", "key": key}))]
            elif name == "delete_key":
                key = args["key"]
                result = self._client.delete(key)
                return [TextContent(type="text", text=json.dumps({"status": "deleted" if result else "not_found", "key": key}))]
            elif name == "flush_all":
                self._client.flush_all()
                return [TextContent(type="text", text=json.dumps({"status": "flushed"}))]
            elif name == "server_stats":
                stats = self._client.stats()
                return [TextContent(type="text", text=json.dumps(stats, default=str))]
            elif name == "get_multi":
                keys = [k.strip() for k in args["keys"].split(",")]
                result = self._client.get_multi(keys)
                decoded = {k: v.decode() if v else None for k, v in result.items()}
                return [TextContent(type="text", text=json.dumps(decoded))]
            elif name == "set_multi":
                items = json.loads(args["items_json"])
                self._client.set_multi(items)
                return [TextContent(type="text", text=json.dumps({"status": "set", "keys": list(items.keys())}))]
            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, default=str))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = MemcachedServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
