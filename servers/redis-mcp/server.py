import json
import os

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
import redis.asyncio as redis


class RedisServer(Server):
    def __init__(self):
        super().__init__("redis")
        self._redis = None

    def _init_env(self):
        self._redis_host = os.environ.get("REDIS_HOST", "localhost")
        self._redis_port = int(os.environ.get("REDIS_PORT", 6379))
        self._redis_password = os.environ.get("REDIS_PASSWORD", None)
        self._redis_db = int(os.environ.get("REDIS_DB", 0))

    async def _get_client(self) -> redis.Redis:
        if self._redis is None:
            self._init_env()
            self._redis = redis.Redis(
                host=self._redis_host,
                port=self._redis_port,
                password=self._redis_password,
                db=self._redis_db,
                decode_responses=True,
            )
        return self._redis

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="get_key", description="Get the string value of a key", inputSchema={"type":"object","properties":{"key":{"type":"string","description":"Key name"}},"required":["key"]}),
            Tool(name="set_key", description="Set a key with optional TTL", inputSchema={"type":"object","properties":{"key":{"type":"string","description":"Key name"},"value":{"type":"string","description":"Value to set"},"ttl":{"type":"integer","description":"TTL in seconds (optional)"}},"required":["key","value"]}),
            Tool(name="delete_key", description="Delete a key", inputSchema={"type":"object","properties":{"key":{"type":"string","description":"Key to delete"}},"required":["key"]}),
            Tool(name="list_keys", description="List keys matching a pattern", inputSchema={"type":"object","properties":{"pattern":{"type":"string","description":"Glob pattern (default: *)"}},"required":[]}),
            Tool(name="get_info", description="Get Redis server info and stats", inputSchema={"type":"object","properties":{}}),
            Tool(name="ping_server", description="Ping Redis server to check connectivity", inputSchema={"type":"object","properties":{}}),
            Tool(name="get_key_ttl", description="Get TTL in seconds for a key (-1 no expiry, -2 key missing)", inputSchema={"type":"object","properties":{"key":{"type":"string","description":"Key name"}},"required":["key"]}),
            Tool(name="increment_key", description="Increment an integer key by a given amount", inputSchema={"type":"object","properties":{"key":{"type":"string","description":"Key name"},"amount":{"type":"integer","description":"Amount to increment by (default: 1)"}},"required":["key"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        r = await self._get_client()
        try:
            if name == "get_key":
                val = await r.get(args["key"])
                return [TextContent(type="text", text=json.dumps({"key": args["key"], "value": val}))]
            if name == "set_key":
                ttl = args.get("ttl")
                if ttl:
                    await r.setex(args["key"], ttl, args["value"])
                else:
                    await r.set(args["key"], args["value"])
                return [TextContent(type="text", text=json.dumps({"key": args["key"], "set": True}))]
            if name == "delete_key":
                deleted = await r.delete(args["key"])
                return [TextContent(type="text", text=json.dumps({"key": args["key"], "deleted": bool(deleted)}))]
            if name == "list_keys":
                pattern = args.get("pattern", "*")
                keys = await r.keys(pattern)
                return [TextContent(type="text", text=json.dumps({"keys": keys, "count": len(keys)}))]
            if name == "get_info":
                info = await r.info()
                return [TextContent(type="text", text=json.dumps(info, default=str))]
            if name == "ping_server":
                pong = await r.ping()
                return [TextContent(type="text", text=json.dumps({"ping": bool(pong)}))]
            if name == "get_key_ttl":
                ttl = await r.ttl(args["key"])
                return [TextContent(type="text", text=json.dumps({"key": args["key"], "ttl": ttl}))]
            if name == "increment_key":
                amount = args.get("amount", 1)
                val = await r.incrby(args["key"], amount)
                return [TextContent(type="text", text=json.dumps({"key": args["key"], "value": val}))]
            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = RedisServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
