import os
import json
import subprocess
import zipfile
import tarfile
import gzip
import bz2
import shutil
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

BASE = os.environ.get("ARCHIVE_PATH", "/data")

def resolve_path(user_path: str, check_exists: bool = True) -> str:
    p = os.path.normpath(os.path.join(BASE, user_path))
    if not p.startswith(os.path.normpath(BASE)):
        raise ValueError("Path traversal denied")
    if check_exists and not os.path.exists(p):
        raise FileNotFoundError(f"Path not found: {p}")
    return p

def resolve_output_path(user_path: str) -> str:
    p = os.path.normpath(os.path.join(BASE, user_path))
    if not p.startswith(os.path.normpath(BASE)):
        raise ValueError("Path traversal denied")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p

server = Server("archive-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="create_archive",
            description="Create archive from files",
            inputSchema={
                "type": "object",
                "properties": {
                    "files": {"type": "array", "items": {"type": "string"}, "description": "List of file paths to archive"},
                    "output": {"type": "string", "description": "Output archive path"},
                    "format": {"type": "string", "description": "Archive format (zip/tar.gz/tar.bz2/7z)", "default": "zip"}
                },
                "required": ["files", "output"]
            }
        ),
        Tool(
            name="extract_archive",
            description="Extract an archive",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Archive file path"},
                    "output_dir": {"type": "string", "description": "Output directory"},
                    "format": {"type": "string", "description": "Archive format (zip/tar.gz/tar.bz2/7z)"}
                },
                "required": ["input", "output_dir"]
            }
        ),
        Tool(
            name="list_archive",
            description="List contents of an archive",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Archive file path"}
                },
                "required": ["input"]
            }
        ),
        Tool(
            name="compress_file",
            description="Compress a single file with gzip or bzip2",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "File to compress"},
                    "algorithm": {"type": "string", "description": "Compression algorithm (gz/bz2)", "default": "gz"}
                },
                "required": ["input"]
            }
        ),
        Tool(
            name="decompress_file",
            description="Decompress .gz or .bz2 file",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Compressed file path"},
                    "output": {"type": "string", "description": "Output file path"}
                },
                "required": ["input", "output"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "create_archive":
        files = [resolve_path(f) for f in arguments["files"]]
        out = resolve_output_path(arguments["output"])
        fmt = arguments.get("format", "zip")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if fmt == "zip":
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    arcname = os.path.relpath(f, os.path.commonpath(files)) if len(files) > 1 else os.path.basename(f)
                    zf.write(f, arcname)
        elif fmt in ("tar.gz", "tar.bz2"):
            mode = "w:gz" if fmt == "tar.gz" else "w:bz2"
            with tarfile.open(out, mode) as tf:
                for f in files:
                    arcname = os.path.relpath(f, os.path.commonpath(files)) if len(files) > 1 else os.path.basename(f)
                    tf.add(f, arcname)
        elif fmt == "7z":
            file_list_path = out + ".filelist"
            with open(file_list_path, "w") as fl:
                for f in files:
                    fl.write(f + "\n")
            subprocess.run(["7z", "a", out, f"@{file_list_path}"], check=True, capture_output=True)
            os.remove(file_list_path)
        else:
            raise ValueError(f"Unsupported format: {fmt}")
        return [TextContent(type="text", text=json.dumps({"status": "ok", "output": out}))]
    elif name == "extract_archive":
        inp = resolve_path(arguments["input"])
        out_dir = resolve_output_path(arguments["output_dir"])
        os.makedirs(out_dir, exist_ok=True)
        ext = os.path.splitext(inp)[1].lower()
        if ext == ".zip":
            with zipfile.ZipFile(inp, "r") as zf:
                zf.extractall(out_dir)
        elif ext in (".gz", ".bz2"):
            fmt = arguments.get("format", "gz")
            if fmt == "tar.gz" or (ext == ".gz" and inp.endswith(".tar.gz")):
                with tarfile.open(inp, "r:gz") as tf:
                    tf.extractall(out_dir)
            elif ext == ".bz2" or fmt == "tar.bz2":
                with tarfile.open(inp, "r:bz2") as tf:
                    tf.extractall(out_dir)
            else:
                raise ValueError(f"Cannot determine archive type: {inp}")
        elif ext == ".7z":
            subprocess.run(["7z", "x", inp, f"-o{out_dir}"], check=True, capture_output=True)
        else:
            if arguments.get("format") == "tar.gz":
                with tarfile.open(inp, "r:gz") as tf:
                    tf.extractall(out_dir)
            elif arguments.get("format") == "tar.bz2":
                with tarfile.open(inp, "r:bz2") as tf:
                    tf.extractall(out_dir)
            else:
                raise ValueError(f"Unsupported format for: {inp}")
        return [TextContent(type="text", text=json.dumps({"status": "ok", "output_dir": out_dir}))]
    elif name == "list_archive":
        inp = resolve_path(arguments["input"])
        ext = os.path.splitext(inp)[1].lower()
        contents = []
        if zipfile.is_zipfile(inp):
            with zipfile.ZipFile(inp, "r") as zf:
                for zi in zf.infolist():
                    contents.append({"name": zi.filename, "size": zi.file_size, "compressed": zi.compress_size})
        elif tarfile.is_tarfile(inp):
            with tarfile.open(inp, "r") as tf:
                for ti in tf.getmembers():
                    contents.append({"name": ti.name, "size": ti.size, "type": "directory" if ti.isdir() else "file"})
        else:
            result = subprocess.run(["7z", "l", inp], capture_output=True, text=True)
            return [TextContent(type="text", text=result.stdout)]
        return [TextContent(type="text", text=json.dumps(contents, indent=2))]
    elif name == "compress_file":
        inp = resolve_path(arguments["input"])
        algo = arguments.get("algorithm", "gz")
        out = inp + (".gz" if algo == "gz" else ".bz2")
        with open(inp, "rb") as f:
            data = f.read()
        if algo == "gz":
            compressed = gzip.compress(data)
        else:
            compressed = bz2.compress(data)
        with open(out, "wb") as f:
            f.write(compressed)
        return [TextContent(type="text", text=json.dumps({"status": "ok", "output": out, "original_size": len(data), "compressed_size": len(compressed)}))]
    elif name == "decompress_file":
        inp = resolve_path(arguments["input"])
        out = resolve_output_path(arguments["output"])
        with open(inp, "rb") as f:
            data = f.read()
        ext = os.path.splitext(inp)[1].lower()
        if ext == ".gz":
            decompressed = gzip.decompress(data)
        elif ext == ".bz2":
            decompressed = bz2.decompress(data)
        else:
            raise ValueError(f"Unsupported compression format: {ext}")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(decompressed)
        return [TextContent(type="text", text=json.dumps({"status": "ok", "output": out, "size": len(decompressed)}))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="archive-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
