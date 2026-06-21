import os
import sqlite3
import json
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("sqlite-mcp")

ALLOWED_DIR = os.environ.get("SQLITE_DB_DIR", "/data")

def _resolve_db(path: str) -> str:
    base = Path(ALLOWED_DIR).resolve()
    target = (base / path).resolve()
    if not str(target).startswith(str(base)):
        raise PermissionError(f"Database path {path} is outside allowed directory")
    return str(target)

def _dict_factory(cursor, row):
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_databases",
            description="List all .db files in the allowed directory",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="execute_query",
            description="Execute a SQL query (SELECT, INSERT, UPDATE, DELETE). DDL is auto-detected and committed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {"type": "string", "description": "Path to .db file relative to allowed directory"},
                    "query": {"type": "string", "description": "SQL query to execute"},
                },
                "required": ["database", "query"]
            }
        ),
        Tool(
            name="list_tables",
            description="List all tables in a database",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {"type": "string", "description": "Path to .db file"}
                },
                "required": ["database"]
            }
        ),
        Tool(
            name="describe_table",
            description="Get column info for a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {"type": "string", "description": "Path to .db file"},
                    "table": {"type": "string", "description": "Table name"}
                },
                "required": ["database", "table"]
            }
        ),
        Tool(
            name="create_database",
            description="Create a new SQLite database file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path for new .db file"}
                },
                "required": ["path"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = ""

    if name == "list_databases":
        base = Path(ALLOWED_DIR).resolve()
        dbs = [str(p.relative_to(base)) for p in base.rglob("*.db") if p.is_file()]
        result = str(dbs)

    elif name == "execute_query":
        db_path = _resolve_db(arguments["database"])
        query = arguments["query"].strip()
        conn = sqlite3.connect(db_path)
        conn.row_factory = _dict_factory
        try:
            cur = conn.cursor()
            if query.upper().startswith("SELECT") or query.upper().startswith("PRAGMA"):
                cur.execute(query)
                rows = cur.fetchall()
                result = json.dumps(rows, default=str)
            elif query.upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")):
                cur.execute(query)
                conn.commit()
                result = json.dumps({
                    "affected_rows": cur.rowcount,
                    "last_insert_rowid": cur.lastrowid,
                }, default=str)
            else:
                cur.execute(query)
                conn.commit()
                result = json.dumps({"status": "executed"})
        finally:
            conn.close()

    elif name == "list_tables":
        db_path = _resolve_db(arguments["database"])
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            result = str([row[0] for row in cur.fetchall()])
        finally:
            conn.close()

    elif name == "describe_table":
        db_path = _resolve_db(arguments["database"])
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({arguments['table']})")
            cols = cur.fetchall()
            result = str([{"cid": r[0], "name": r[1], "type": r[2], "notnull": bool(r[3]), "default": r[4], "pk": bool(r[5])} for r in cols])
        finally:
            conn.close()

    elif name == "create_database":
        db_path = _resolve_db(arguments["path"])
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.close()
        result = f"Database created at {arguments['path']}"

    else:
        raise ValueError(f"Unknown tool: {name}")

    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="sqlite-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
