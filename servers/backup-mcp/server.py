import os
import json
import subprocess
import time
import shutil
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

SOURCE = os.environ.get("BACKUP_SOURCE", "/data")
DEST = os.environ.get("BACKUP_DEST", "/backup")

def resolve_source(user_path: str) -> str:
    p = os.path.normpath(os.path.join(SOURCE, user_path))
    if not p.startswith(os.path.normpath(SOURCE)):
        raise ValueError("Path traversal denied")
    if not os.path.exists(p):
        raise FileNotFoundError(f"Path not found: {p}")
    return p

def resolve_dest(user_path: str) -> str:
    p = os.path.normpath(os.path.join(DEST, user_path))
    if not p.startswith(os.path.normpath(DEST)):
        raise ValueError("Path traversal denied")
    return p

server = Server("backup-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="backup_files",
            description="Copy files with rsync (dry-run support)",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source path relative to BACKUP_SOURCE"},
                    "dest": {"type": "string", "description": "Destination path relative to BACKUP_DEST"},
                    "exclude": {"type": "array", "items": {"type": "string"}, "description": "Patterns to exclude"},
                    "dry_run": {"type": "boolean", "description": "Perform dry run only", "default": False}
                },
                "required": ["source", "dest"]
            }
        ),
        Tool(
            name="rotate_backups",
            description="Rotate backup directories keeping last N",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Backup directory path relative to BACKUP_DEST"},
                    "keep_count": {"type": "integer", "description": "Number of backups to keep"}
                },
                "required": ["path", "keep_count"]
            }
        ),
        Tool(
            name="incremental_copy",
            description="Copy only changed files since last backup",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source path relative to BACKUP_SOURCE"},
                    "dest": {"type": "string", "description": "Destination path relative to BACKUP_DEST"},
                    "manifest_file": {"type": "string", "description": "Path to manifest file tracking changes"}
                },
                "required": ["source", "dest"]
            }
        ),
        Tool(
            name="backup_info",
            description="Show backup directory statistics",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Backup path relative to BACKUP_DEST"}
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
    if name == "backup_files":
        src = resolve_source(arguments["source"])
        dst = resolve_dest(arguments["dest"])
        os.makedirs(dst, exist_ok=True)
        cmd = ["rsync", "-av"]
        for ex in arguments.get("exclude", []):
            cmd.extend(["--exclude", ex])
        if arguments.get("dry_run", False):
            cmd.append("--dry-run")
        cmd.extend([src + "/", dst + "/"])
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"rsync error: {result.stderr}")
        return [TextContent(type="text", text=result.stdout)]
    elif name == "rotate_backups":
        bp = resolve_dest(arguments["path"])
        keep = arguments["keep_count"]
        if not os.path.isdir(bp):
            raise FileNotFoundError(f"Directory not found: {bp}")
        entries = sorted(
            [os.path.join(bp, d) for d in os.listdir(bp) if os.path.isdir(os.path.join(bp, d))],
            key=os.path.getmtime
        )
        to_delete = entries[:-keep] if len(entries) > keep else []
        for d in to_delete:
            shutil.rmtree(d)
        return [TextContent(type="text", text=json.dumps({
            "kept": len(entries) - len(to_delete),
            "deleted": len(to_delete),
            "deleted_dirs": to_delete
        }))]
    elif name == "incremental_copy":
        src = resolve_source(arguments["source"])
        dst = resolve_dest(arguments["dest"])
        manifest = arguments["manifest_file"]
        os.makedirs(dst, exist_ok=True)
        manifest_path = os.path.join(BASE := os.path.dirname(dst), manifest) if "/" not in manifest and "\\" not in manifest else resolve_dest(manifest)
        manifest_dir = os.path.dirname(manifest_path)
        os.makedirs(manifest_dir, exist_ok=True)
        cmd = ["rsync", "-av", "--delete", "--link-dest=" + dst, src + "/", dst + "/"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"rsync error: {result.stderr}")
        timestamp = time.time()
        with open(manifest_path, "a") as mf:
            mf.write(f"{timestamp} backup: {src} -> {dst}\n")
        return [TextContent(type="text", text=json.dumps({
            "status": "ok",
            "source": src,
            "dest": dst,
            "manifest": manifest_path,
            "output": result.stdout
        }))]
    elif name == "backup_info":
        bp = resolve_dest(arguments["path"])
        if not os.path.exists(bp):
            raise FileNotFoundError(f"Path not found: {bp}")
        total_size = 0
        file_count = 0
        last_modified = 0
        for root, dirs, files in os.walk(bp):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    st = os.stat(fp)
                    total_size += st.st_size
                    file_count += 1
                    if st.st_mtime > last_modified:
                        last_modified = st.st_mtime
                except OSError:
                    pass
        return [TextContent(type="text", text=json.dumps({
            "path": bp,
            "size_bytes": total_size,
            "size_human": f"{total_size / (1024**3):.2f} GB" if total_size > 1024**3 else f"{total_size / (1024**2):.2f} MB",
            "file_count": file_count,
            "last_modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_modified))
        }))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="backup-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
