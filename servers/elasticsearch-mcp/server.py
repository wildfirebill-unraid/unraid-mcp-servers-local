import json
import os

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
from elasticsearch import AsyncElasticsearch


class ElasticsearchServer(Server):
    def __init__(self):
        super().__init__("elasticsearch")
        self._init_env()

    def _init_env(self):
        host = os.environ.get("ES_HOST", "localhost")
        port = os.environ.get("ES_PORT", "9200")
        self._es = AsyncElasticsearch(f"http://{host}:{port}")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="cluster_health", description="Cluster health status", inputSchema={"type": "object", "properties": {}}),
            Tool(name="list_indices", description="List all indices", inputSchema={"type": "object", "properties": {}}),
            Tool(name="search", description="Search with DSL query JSON", inputSchema={"type": "object", "properties": {"index": {"type": "string", "description": "Index name"}, "query_json": {"type": "string", "description": "Query DSL JSON"}}, "required": ["index", "query_json"]}),
            Tool(name="get_document", description="Get document by ID", inputSchema={"type": "object", "properties": {"index": {"type": "string", "description": "Index name"}, "doc_id": {"type": "string", "description": "Document ID"}}, "required": ["index", "doc_id"]}),
            Tool(name="index_document", description="Index a document", inputSchema={"type": "object", "properties": {"index": {"type": "string", "description": "Index name"}, "doc_json": {"type": "string", "description": "Document body JSON"}, "doc_id": {"type": "string", "description": "Document ID (optional)"}}, "required": ["index", "doc_json"]}),
            Tool(name="delete_index", description="Delete an index", inputSchema={"type": "object", "properties": {"index": {"type": "string", "description": "Index name"}}, "required": ["index"]}),
            Tool(name="get_mapping", description="Get index mapping", inputSchema={"type": "object", "properties": {"index": {"type": "string", "description": "Index name"}}, "required": ["index"]}),
            Tool(name="get_index_stats", description="Index statistics", inputSchema={"type": "object", "properties": {"index": {"type": "string", "description": "Index name"}}, "required": ["index"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "cluster_health":
                result = await self._es.cluster.health()
                return [TextContent(type="text", text=json.dumps(result.body, default=str))]
            elif name == "list_indices":
                result = await self._es.indices.get_alias(index="*")
                indices = sorted(result.body.keys())
                return [TextContent(type="text", text=json.dumps(indices, default=str))]
            elif name == "search":
                index = args["index"]
                query = json.loads(args["query_json"])
                result = await self._es.search(index=index, body=query)
                return [TextContent(type="text", text=json.dumps(result.body, default=str))]
            elif name == "get_document":
                index = args["index"]
                doc_id = args["doc_id"]
                result = await self._es.get(index=index, id=doc_id)
                return [TextContent(type="text", text=json.dumps(result.body, default=str))]
            elif name == "index_document":
                index = args["index"]
                doc = json.loads(args["doc_json"])
                doc_id = args.get("doc_id")
                if doc_id:
                    result = await self._es.index(index=index, id=doc_id, body=doc)
                else:
                    result = await self._es.index(index=index, body=doc)
                return [TextContent(type="text", text=json.dumps(result.body, default=str))]
            elif name == "delete_index":
                index = args["index"]
                result = await self._es.indices.delete(index=index)
                return [TextContent(type="text", text=json.dumps(result.body, default=str))]
            elif name == "get_mapping":
                index = args["index"]
                result = await self._es.indices.get_mapping(index=index)
                return [TextContent(type="text", text=json.dumps(result.body, default=str))]
            elif name == "get_index_stats":
                index = args["index"]
                result = await self._es.indices.stats(index=index)
                return [TextContent(type="text", text=json.dumps(result.body, default=str))]
            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, default=str))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = ElasticsearchServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
