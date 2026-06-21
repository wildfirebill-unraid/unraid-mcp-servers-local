import json
import os

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
import pymongo


class MongodbServer(Server):
    def __init__(self):
        super().__init__("mongodb")
        self._client = None

    def _init_env(self):
        self._mongodb_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        self._mongodb_database = os.environ.get("MONGODB_DATABASE", "test")

    def _get_db(self):
        if self._client is None:
            self._init_env()
            self._client = pymongo.MongoClient(self._mongodb_uri, serverSelectionTimeoutMS=5000)
        return self._client[self._mongodb_database]

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="list_databases", description="List all databases on the server", inputSchema={"type":"object","properties":{}}),
            Tool(name="list_collections", description="List collections in the configured database", inputSchema={"type":"object","properties":{}}),
            Tool(name="find_documents", description="Query documents in a collection", inputSchema={"type":"object","properties":{"collection":{"type":"string","description":"Collection name"},"filter_json":{"type":"string","description":"MongoDB filter as JSON (default: {})"},"limit":{"type":"integer","description":"Max documents to return (default: 100)"},"skip":{"type":"integer","description":"Documents to skip (default: 0)"}},"required":["collection"]}),
            Tool(name="insert_document", description="Insert a document into a collection", inputSchema={"type":"object","properties":{"collection":{"type":"string","description":"Collection name"},"document_json":{"type":"string","description":"Document as JSON"}},"required":["collection","document_json"]}),
            Tool(name="update_document", description="Update documents matching a filter", inputSchema={"type":"object","properties":{"collection":{"type":"string","description":"Collection name"},"filter_json":{"type":"string","description":"MongoDB filter as JSON"},"update_json":{"type":"string","description":"MongoDB update operation as JSON"}},"required":["collection","filter_json","update_json"]}),
            Tool(name="delete_document", description="Delete documents matching a filter", inputSchema={"type":"object","properties":{"collection":{"type":"string","description":"Collection name"},"filter_json":{"type":"string","description":"MongoDB filter as JSON"}},"required":["collection","filter_json"]}),
            Tool(name="aggregate", description="Run an aggregation pipeline", inputSchema={"type":"object","properties":{"collection":{"type":"string","description":"Collection name"},"pipeline_json":{"type":"string","description":"Aggregation pipeline as JSON array"}},"required":["collection","pipeline_json"]}),
            Tool(name="collection_stats", description="Get collection statistics", inputSchema={"type":"object","properties":{"collection":{"type":"string","description":"Collection name"}},"required":["collection"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        db = self._get_db()
        try:
            if name == "list_databases":
                dbs = self._client.list_database_names()
                return [TextContent(type="text", text=json.dumps({"databases": dbs}, default=str))]
            if name == "list_collections":
                cols = db.list_collection_names()
                return [TextContent(type="text", text=json.dumps({"collections": cols}, default=str))]
            if name == "find_documents":
                coll = args["collection"]
                filt = json.loads(args.get("filter_json", "{}"))
                limit = args.get("limit", 100)
                skip = args.get("skip", 0)
                docs = list(db[coll].find(filt).skip(skip).limit(limit))
                for d in docs:
                    d["_id"] = str(d["_id"])
                return [TextContent(type="text", text=json.dumps({"documents": docs, "count": len(docs)}, default=str))]
            if name == "insert_document":
                coll = args["collection"]
                doc = json.loads(args["document_json"])
                result = db[coll].insert_one(doc)
                return [TextContent(type="text", text=json.dumps({"inserted_id": str(result.inserted_id)}, default=str))]
            if name == "update_document":
                coll = args["collection"]
                filt = json.loads(args["filter_json"])
                upd = json.loads(args["update_json"])
                result = db[coll].update_many(filt, upd)
                return [TextContent(type="text", text=json.dumps({"matched": result.matched_count, "modified": result.modified_count}, default=str))]
            if name == "delete_document":
                coll = args["collection"]
                filt = json.loads(args["filter_json"])
                result = db[coll].delete_many(filt)
                return [TextContent(type="text", text=json.dumps({"deleted": result.deleted_count}, default=str))]
            if name == "aggregate":
                coll = args["collection"]
                pipeline = json.loads(args["pipeline_json"])
                docs = list(db[coll].aggregate(pipeline))
                for d in docs:
                    if "_id" in d:
                        d["_id"] = str(d["_id"])
                return [TextContent(type="text", text=json.dumps({"results": docs, "count": len(docs)}, default=str))]
            if name == "collection_stats":
                coll = args["collection"]
                stats = db.command("collStats", coll)
                return [TextContent(type="text", text=json.dumps(stats, default=str))]
            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = MongodbServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
