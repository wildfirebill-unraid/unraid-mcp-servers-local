import os
import json
import docker
from docker.errors import DockerException
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("docker-mcp")

DOCKER_HOST = os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")

def get_client():
    try:
        return docker.DockerClient(base_url=DOCKER_HOST)
    except DockerException as e:
        raise RuntimeError(f"Cannot connect to Docker: {e}")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_containers",
            description="List Docker containers with status and info",
            inputSchema={
                "type": "object",
                "properties": {
                    "all": {"type": "boolean", "description": "Include stopped containers (default true)"}
                },
                "required": []
            }
        ),
        Tool(
            name="inspect_container",
            description="Get detailed information about a container",
            inputSchema={
                "type": "object",
                "properties": {
                    "container_id": {"type": "string", "description": "Container ID or name"}
                },
                "required": ["container_id"]
            }
        ),
        Tool(
            name="container_logs",
            description="Get logs from a container",
            inputSchema={
                "type": "object",
                "properties": {
                    "container_id": {"type": "string", "description": "Container ID or name"},
                    "tail": {"type": "integer", "description": "Number of lines to return (default 50)"}
                },
                "required": ["container_id"]
            }
        ),
        Tool(
            name="start_container",
            description="Start a stopped container",
            inputSchema={
                "type": "object",
                "properties": {
                    "container_id": {"type": "string", "description": "Container ID or name"}
                },
                "required": ["container_id"]
            }
        ),
        Tool(
            name="stop_container",
            description="Stop a running container",
            inputSchema={
                "type": "object",
                "properties": {
                    "container_id": {"type": "string", "description": "Container ID or name"}
                },
                "required": ["container_id"]
            }
        ),
        Tool(
            name="restart_container",
            description="Restart a container",
            inputSchema={
                "type": "object",
                "properties": {
                    "container_id": {"type": "string", "description": "Container ID or name"}
                },
                "required": ["container_id"]
            }
        ),
        Tool(
            name="list_images",
            description="List Docker images",
            inputSchema={
                "type": "object",
                "properties": {
                    "dangling": {"type": "boolean", "description": "Show only dangling images"}
                },
                "required": []
            }
        ),
        Tool(
            name="container_stats",
            description="Get live resource usage stats for a container",
            inputSchema={
                "type": "object",
                "properties": {
                    "container_id": {"type": "string", "description": "Container ID or name"}
                },
                "required": ["container_id"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    client = get_client()
    result = ""

    try:
        if name == "list_containers":
            show_all = arguments.get("all", True)
            containers = client.containers.list(all=show_all)
            result = str([
                {
                    "id": c.short_id,
                    "name": c.name,
                    "image": c.image.tags[0] if c.image.tags else "none",
                    "status": c.status,
                    "state": c.attrs["State"]["Status"],
                    "ports": c.attrs["NetworkSettings"]["Ports"],
                    "created": c.attrs["Created"],
                }
                for c in containers
            ])

        elif name == "inspect_container":
            c = client.containers.get(arguments["container_id"])
            result = json.dumps(c.attrs, default=str, indent=2)

        elif name == "container_logs":
            c = client.containers.get(arguments["container_id"])
            tail = arguments.get("tail", 50)
            logs = c.logs(tail=tail, timestamps=True)
            result = logs.decode("utf-8", errors="replace")

        elif name == "start_container":
            c = client.containers.get(arguments["container_id"])
            c.start()
            result = f"Started container {arguments['container_id']}"

        elif name == "stop_container":
            c = client.containers.get(arguments["container_id"])
            c.stop()
            result = f"Stopped container {arguments['container_id']}"

        elif name == "restart_container":
            c = client.containers.get(arguments["container_id"])
            c.restart()
            result = f"Restarted container {arguments['container_id']}"

        elif name == "list_images":
            dangling = arguments.get("dangling", False)
            filters = {"dangling": True} if dangling else None
            images = client.images.list(filters=filters)
            result = str([
                {
                    "id": img.short_id,
                    "tags": img.tags,
                    "size_mb": round(img.attrs["Size"] / (1024**2), 2) if "Size" in img.attrs else 0,
                    "created": img.attrs.get("Created", ""),
                }
                for img in images
            ])

        elif name == "container_stats":
            c = client.containers.get(arguments["container_id"])
            stats = c.stats(stream=False)
            result = json.dumps({
                "cpu_percent": round(stats["cpu_stats"]["cpu_usage"]["total_usage"] / stats["cpu_stats"]["system_cpu_usage"] * 100, 2) if stats["cpu_stats"].get("system_cpu_usage") else "N/A",
                "memory_usage_mb": round(stats["memory_stats"]["usage"] / (1024**2), 2) if "usage" in stats.get("memory_stats", {}) else 0,
                "memory_limit_mb": round(stats["memory_stats"]["limit"] / (1024**2), 2) if "limit" in stats.get("memory_stats", {}) else 0,
                "network_rx_bytes": stats["networks"].get("eth0", {}).get("rx_bytes", 0) if "networks" in stats else 0,
                "network_tx_bytes": stats["networks"].get("eth0", {}).get("tx_bytes", 0) if "networks" in stats else 0,
            }, default=str, indent=2)

        else:
            raise ValueError(f"Unknown tool: {name}")
    finally:
        client.close()

    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="docker-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
