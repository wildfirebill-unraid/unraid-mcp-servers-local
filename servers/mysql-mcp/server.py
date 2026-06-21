import json
import os
import pymysql
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

class MysqlServer(Server):
    def __init__(self):
        super().__init__("mysql")
        self._init_env()

    def _init_env(self):
        self._conn_params = {
            "host": os.environ.get("MYSQL_HOST", "localhost"),
            "port": int(os.environ.get("MYSQL_PORT", 3306)),
            "user": os.environ.get("MYSQL_USER", "root"),
            "password": os.environ.get("MYSQL_PASSWORD", ""),
            "database": os.environ.get("MYSQL_DATABASE", ""),
        }

    def _get_connection(self):
        return pymysql.connect(**self._conn_params, cursorclass=pymysql.cursors.DictCursor)

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="list_databases", description="List all databases on the server", inputSchema={"type":"object","properties":{}}),
            Tool(name="list_tables", description="List tables in the current database", inputSchema={"type":"object","properties":{}}),
            Tool(name="describe_table", description="Describe a table's columns, types, and keys", inputSchema={"type":"object","properties":{"table":{"type":"string","description":"Table name"}},"required":["table"]}),
            Tool(name="execute_query", description="Execute an arbitrary SELECT query", inputSchema={"type":"object","properties":{"query":{"type":"string","description":"SELECT query to execute"},"params":{"type":"object","description":"Optional query parameters as JSON object"}},"required":["query"]}),
            Tool(name="server_status", description="Get MySQL version, uptime, and connection info", inputSchema={"type":"object","properties":{}}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "list_databases":
                return await self._list_databases()
            if name == "list_tables":
                return await self._list_tables()
            if name == "describe_table":
                return await self._describe_table(args["table"])
            if name == "execute_query":
                return await self._execute_query(args["query"], args.get("params"))
            if name == "server_status":
                return await self._server_status()
            raise ValueError(f"Unknown tool: {name}")
        except pymysql.Error as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def _list_databases(self) -> list[TextContent]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW DATABASES")
                rows = cur.fetchall()
            return [TextContent(type="text", text=json.dumps([list(r.values())[0] for r in rows]))]
        finally:
            conn.close()

    async def _list_tables(self) -> list[TextContent]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES")
                rows = cur.fetchall()
            return [TextContent(type="text", text=json.dumps([list(r.values())[0] for r in rows]))]
        finally:
            conn.close()

    async def _describe_table(self, table: str) -> list[TextContent]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DESCRIBE " + table)
                rows = cur.fetchall()
            return [TextContent(type="text", text=json.dumps(rows))]
        finally:
            conn.close()

    async def _execute_query(self, query: str, params: dict | None) -> list[TextContent]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                if params:
                    cur.execute(query, tuple(params.values()) if isinstance(params, dict) else params)
                else:
                    cur.execute(query)
                if cur.description:
                    rows = cur.fetchall()
                else:
                    rows = {"affected_rows": cur.rowcount}
                conn.commit()
            return [TextContent(type="text", text=json.dumps(rows))]
        finally:
            conn.close()

    async def _server_status(self) -> list[TextContent]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION() AS version, NOW() AS current_time")
                row = cur.fetchone()
                cur.execute("SELECT VARIABLE_VALUE AS uptime_seconds FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME = 'Uptime'")
                uptime_row = cur.fetchone()
                cur.execute("SELECT COUNT(*) AS connections FROM information_schema.PROCESSLIST")
                conn_row = cur.fetchone()
            info = {
                "version": row["version"] if row else None,
                "current_time": str(row["current_time"]) if row else None,
                "uptime_seconds": int(uptime_row["uptime_seconds"]) if uptime_row else None,
                "connections": conn_row["connections"] if conn_row else None,
            }
            return [TextContent(type="text", text=json.dumps(info))]
        finally:
            conn.close()

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = MysqlServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
