import json
import os
import psycopg2
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

class PostgresqlServer(Server):
    def __init__(self):
        super().__init__("postgresql")
        self._init_env()

    def _init_env(self):
        self._conn_params = {
            "host": os.environ.get("PGHOST", "localhost"),
            "port": int(os.environ.get("PGPORT", 5432)),
            "user": os.environ.get("PGUSER", "postgres"),
            "password": os.environ.get("PGPASSWORD", ""),
            "dbname": os.environ.get("PGDATABASE", "postgres"),
        }

    def _get_connection(self):
        return psycopg2.connect(**self._conn_params)

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="list_databases", description="List all databases on the server", inputSchema={"type":"object","properties":{}}),
            Tool(name="list_tables", description="List tables in a schema", inputSchema={"type":"object","properties":{"schema":{"type":"string","description":"Database schema (default: public)"}}}),
            Tool(name="describe_table", description="Describe a table's columns, types, and constraints", inputSchema={"type":"object","properties":{"table":{"type":"string","description":"Table name"},"schema":{"type":"string","description":"Database schema (default: public)"}},"required":["table"]}),
            Tool(name="execute_query", description="Execute an arbitrary SELECT query", inputSchema={"type":"object","properties":{"query":{"type":"string","description":"SELECT query to execute"},"params":{"type":"object","description":"Optional query parameters as JSON object"}},"required":["query"]}),
            Tool(name="get_server_info", description="Get PostgreSQL version, uptime, and connected users", inputSchema={"type":"object","properties":{}}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "list_databases":
                return await self._list_databases()
            if name == "list_tables":
                return await self._list_tables(args.get("schema", "public"))
            if name == "describe_table":
                return await self._describe_table(args["table"], args.get("schema", "public"))
            if name == "execute_query":
                return await self._execute_query(args["query"], args.get("params"))
            if name == "get_server_info":
                return await self._get_server_info()
            raise ValueError(f"Unknown tool: {name}")
        except psycopg2.Error as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def _list_databases(self) -> list[TextContent]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname")
                rows = cur.fetchall()
            return [TextContent(type="text", text=json.dumps([r[0] for r in rows]))]
        finally:
            conn.close()

    async def _list_tables(self, schema: str) -> list[TextContent]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s ORDER BY tablename", (schema,))
                rows = cur.fetchall()
            return [TextContent(type="text", text=json.dumps([r[0] for r in rows]))]
        finally:
            conn.close()

    async def _describe_table(self, table: str, schema: str) -> list[TextContent]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        c.column_name,
                        c.data_type,
                        c.is_nullable,
                        c.column_default,
                        tc.constraint_type
                    FROM information_schema.columns c
                    LEFT JOIN information_schema.constraint_column_usage ccu
                        ON c.column_name = ccu.column_name
                        AND c.table_name = ccu.table_name
                        AND c.table_schema = ccu.table_schema
                    LEFT JOIN information_schema.table_constraints tc
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE c.table_schema = %s AND c.table_name = %s
                    ORDER BY c.ordinal_position
                """, (schema, table))
                rows = cur.fetchall()
                columns = [{"column": r[0], "type": r[1], "nullable": r[2], "default": r[3], "constraint": r[4]} for r in rows]
            return [TextContent(type="text", text=json.dumps(columns))]
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
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    result = [dict(zip(columns, row)) for row in rows]
                else:
                    result = {"affected_rows": cur.rowcount}
                conn.commit()
            return [TextContent(type="text", text=json.dumps(result))]
        finally:
            conn.close()

    async def _get_server_info(self) -> list[TextContent]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT version(), pg_postmaster_start_time(), now() - pg_postmaster_start_time() AS uptime")
                version, start_time, uptime = cur.fetchone()
                cur.execute("SELECT count(*) FROM pg_stat_activity")
                connections = cur.fetchone()[0]
            info = {
                "version": version,
                "start_time": str(start_time),
                "uptime": str(uptime),
                "connected_users": connections,
            }
            return [TextContent(type="text", text=json.dumps(info))]
        finally:
            conn.close()

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = PostgresqlServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
