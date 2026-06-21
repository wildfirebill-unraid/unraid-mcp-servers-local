import json
import os

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS


class InfluxdbServer(Server):
    def __init__(self):
        super().__init__("influxdb")
        self._init_env()

    def _init_env(self):
        url = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
        token = os.environ.get("INFLUXDB_TOKEN", "")
        org = os.environ.get("INFLUXDB_ORG", "")
        self._org = org
        self._client = InfluxDBClient(url=url, token=token, org=org)

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="list_buckets", description="List all buckets", inputSchema={"type": "object", "properties": {}}),
            Tool(name="write_point", description="Write a data point", inputSchema={"type": "object", "properties": {"bucket": {"type": "string", "description": "Bucket name"}, "measurement": {"type": "string", "description": "Measurement name"}, "fields_json": {"type": "string", "description": "Fields as JSON object"}, "tags_json": {"type": "string", "description": "Tags as JSON object (optional)"}, "timestamp": {"type": "string", "description": "Timestamp in RFC3339 (optional)"}}, "required": ["bucket", "measurement", "fields_json"]}),
            Tool(name="query_flux", description="Execute Flux query", inputSchema={"type": "object", "properties": {"bucket": {"type": "string", "description": "Bucket to query"}, "flux_query": {"type": "string", "description": "Flux query string"}}, "required": ["bucket", "flux_query"]}),
            Tool(name="list_measurements", description="List measurements in a bucket", inputSchema={"type": "object", "properties": {"bucket": {"type": "string", "description": "Bucket name"}}, "required": ["bucket"]}),
            Tool(name="delete_data", description="Delete data from a bucket", inputSchema={"type": "object", "properties": {"bucket": {"type": "string", "description": "Bucket name"}, "start": {"type": "string", "description": "Start time RFC3339"}, "stop": {"type": "string", "description": "Stop time RFC3339"}, "predicate": {"type": "string", "description": "Delete predicate (optional)"}}, "required": ["bucket", "start", "stop"]}),
            Tool(name="get_health", description="Health check", inputSchema={"type": "object", "properties": {}}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "list_buckets":
                buckets = self._client.buckets_api().find_buckets().buckets
                data = [{"id": b.id, "name": b.name, "type": str(b.type)} for b in buckets]
                return [TextContent(type="text", text=json.dumps(data, default=str))]
            elif name == "write_point":
                bucket = args["bucket"]
                measurement = args["measurement"]
                fields = json.loads(args["fields_json"])
                tags = json.loads(args.get("tags_json", "{}"))
                ts = args.get("timestamp")
                from influxdb_client import Point
                point = Point(measurement).tag(tags).field(fields)
                if ts:
                    point = point.time(ts)
                with self._client.write_api(write_options=SYNCHRONOUS) as write_api:
                    write_api.write(bucket=bucket, record=point)
                return [TextContent(type="text", text=json.dumps({"status": "written"}))]
            elif name == "query_flux":
                bucket = args["bucket"]
                query = args["flux_query"]
                full_query = f'from(bucket:"{bucket}")\n|> {query}'
                tables = self._client.query_api().query(full_query)
                data = []
                for table in tables:
                    for record in table.records:
                        data.append(record.values)
                return [TextContent(type="text", text=json.dumps(data, default=str))]
            elif name == "list_measurements":
                bucket = args["bucket"]
                query = f'from(bucket:"{bucket}") |> range(start:0) |> keep(columns: ["_measurement"]) |> distinct(column: "_measurement")'
                tables = self._client.query_api().query(query)
                measurements = set()
                for table in tables:
                    for record in table.records:
                        measurements.add(record.get_value())
                return [TextContent(type="text", text=json.dumps(sorted(measurements), default=str))]
            elif name == "delete_data":
                bucket = args["bucket"]
                start = args["start"]
                stop = args["stop"]
                predicate = args.get("predicate", "")
                self._client.delete_api().delete(
                    start, stop, predicate, bucket=bucket, org=self._org
                )
                return [TextContent(type="text", text=json.dumps({"status": "deleted"}))]
            elif name == "get_health":
                health = self._client.health()
                return [TextContent(type="text", text=json.dumps({"status": health.status}, default=str))]
            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, default=str))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = InfluxdbServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
