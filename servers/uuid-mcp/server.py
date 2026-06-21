import os
import json
import uuid as uuid_lib
from datetime import datetime, timezone
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("uuid-mcp")

BASE_PATH = Path(os.environ.get("UUID_MCP_PATH", "/data"))

KNOWN_NAMESPACES = {
    "dns": uuid_lib.NAMESPACE_DNS,
    "url": uuid_lib.NAMESPACE_URL,
    "oid": uuid_lib.NAMESPACE_OID,
    "x500": uuid_lib.NAMESPACE_X500,
}

def _uuid_to_timestamp(u: uuid_lib.UUID) -> str | None:
    if u.version == 1:
        ts = u.time
        unix_ts = (ts - 0x01b21dd213814000) / 1e7
        return datetime.fromtimestamp(unix_ts, tz=timezone.utc).isoformat()
    if u.version == 7:
        unix_ts = u.time >> 80
        return datetime.fromtimestamp(unix_ts / 1000, tz=timezone.utc).isoformat()
    return None

def _uuid_name(u: uuid_lib.UUID) -> str | None:
    for name, ns in KNOWN_NAMESPACES.items():
        if u == ns:
            return name
    return None

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="generate_uuid",
            description="Generate UUID(s)",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of UUIDs to generate", "default": 1},
                    "version": {"type": "integer", "description": "UUID version (4=random, 7=time-ordered)", "default": 4},
                },
            },
        ),
        Tool(
            name="validate_uuid",
            description="Validate a UUID string",
            inputSchema={
                "type": "object",
                "properties": {
                    "uuid_str": {"type": "string", "description": "UUID string to validate"},
                },
                "required": ["uuid_str"],
            },
        ),
        Tool(
            name="uuid_info",
            description="Get info about a UUID (version, variant, timestamp)",
            inputSchema={
                "type": "object",
                "properties": {
                    "uuid_str": {"type": "string", "description": "UUID string"},
                },
                "required": ["uuid_str"],
            },
        ),
        Tool(
            name="uuid_v5",
            description="Generate UUID v5 (namespace + name)",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name to hash"},
                    "namespace": {"type": "string", "description": "Namespace: url, dns, oid, x500, or custom UUID"},
                },
                "required": ["name", "namespace"],
            },
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "generate_uuid":
        count = arguments.get("count", 1)
        version = arguments.get("version", 4)
        count = max(1, min(count, 100))
        uuids = []
        for _ in range(count):
            if version == 7:
                uuids.append(str(uuid_lib.uuid7()))
            else:
                uuids.append(str(uuid_lib.uuid4()))
        result = json.dumps({"uuids": uuids, "count": count, "version": version}, indent=2)

    elif name == "validate_uuid":
        uuid_str = arguments["uuid_str"]
        try:
            u = uuid_lib.UUID(uuid_str)
            result = json.dumps({"valid": True, "version": u.version, "uuid": str(u)}, indent=2)
        except ValueError:
            result = json.dumps({"valid": False, "uuid": uuid_str}, indent=2)

    elif name == "uuid_info":
        uuid_str = arguments["uuid_str"]
        try:
            u = uuid_lib.UUID(uuid_str)
            ts = _uuid_to_timestamp(u)
            info = {
                "uuid": str(u),
                "version": u.version,
                "variant": str(u.variant),
                "hex": u.hex,
                "urn": f"urn:uuid:{u}",
            }
            if u.version == 1:
                info["timestamp"] = ts
                info["clock_seq"] = u.clock_seq
                info["node"] = f"{u.node:012x}"
            if u.version == 7:
                info["timestamp"] = ts
            result = json.dumps(info, indent=2)
        except ValueError as e:
            result = json.dumps({"error": str(e)}, indent=2)

    elif name == "uuid_v5":
        name = arguments["name"]
        namespace_str = arguments["namespace"]
        ns = KNOWN_NAMESPACES.get(namespace_str.lower())
        if ns is None:
            try:
                ns = uuid_lib.UUID(namespace_str)
            except ValueError:
                result = json.dumps({"error": f"Unknown namespace: {namespace_str}"}, indent=2)
                return [TextContent(type="text", text=result)]
        u = uuid_lib.uuid5(ns, name)
        result = json.dumps({"uuid": str(u), "version": 5, "namespace": namespace_str, "name": name}, indent=2)

    else:
        result = f"Unknown tool: {name}"

    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="uuid-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
