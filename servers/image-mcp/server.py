import os
import json
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio
from PIL import Image, ExifTags

BASE = Path(os.environ.get("IMAGE_BASE_PATH", "/data"))
server = Server("image-mcp")

def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else BASE / path

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="image_info", description="Get image metadata", inputSchema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}),
        Tool(name="image_resize", description="Resize image", inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "width": {"type": "integer"}, "height": {"type": "integer"}, "output": {"type": "string"}, "maintain_aspect": {"type": "boolean", "default": True}}, "required": ["path", "width", "height", "output"]}),
        Tool(name="image_convert", description="Convert image format", inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "output_format": {"type": "string", "enum": ["jpeg", "png", "webp", "gif"]}, "output": {"type": "string"}, "quality": {"type": "integer", "default": 90}}, "required": ["path", "output_format", "output"]}),
        Tool(name="image_thumbnail", description="Create thumbnail", inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "max_size": {"type": "integer", "default": 200}, "output": {"type": "string"}}, "required": ["path", "output"]}),
        Tool(name="image_info_batch", description="Get info for multiple images matching glob", inputSchema={"type": "object", "properties": {"directory": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["directory", "pattern"]}),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

def _get_info(img: Image.Image, path: str) -> dict:
    exif = {}
    try:
        raw = img.getexif()
        for tag_id, value in raw.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            exif[tag] = str(value)
    except Exception:
        pass
    return {"path": path, "format": img.format, "size": img.size, "mode": img.mode, "exif": exif}

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "image_info":
        path = _resolve(arguments["path"])
        img = Image.open(path)
        return [TextContent(type="text", text=json.dumps(_get_info(img, str(path)), indent=2))]
    elif name == "image_resize":
        path = _resolve(arguments["path"])
        output = _resolve(arguments["output"])
        img = Image.open(path)
        w, h = arguments["width"], arguments["height"]
        if arguments.get("maintain_aspect", True):
            img.thumbnail((w, h), Image.LANCZOS)
        else:
            img = img.resize((w, h), Image.LANCZOS)
        img.save(str(output))
        return [TextContent(type="text", text=json.dumps({"saved": str(output), "size": img.size}))]
    elif name == "image_convert":
        path = _resolve(arguments["path"])
        output = _resolve(arguments["output"])
        fmt = arguments["output_format"]
        quality = arguments.get("quality", 90)
        img = Image.open(path)
        if fmt == "jpeg":
            img = img.convert("RGB")
        img.save(str(output), format=fmt.upper(), quality=quality)
        return [TextContent(type="text", text=json.dumps({"saved": str(output), "format": fmt}))]
    elif name == "image_thumbnail":
        path = _resolve(arguments["path"])
        output = _resolve(arguments["output"])
        max_size = arguments.get("max_size", 200)
        img = Image.open(path)
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        img.save(str(output))
        return [TextContent(type="text", text=json.dumps({"saved": str(output), "size": img.size}))]
    elif name == "image_info_batch":
        directory = _resolve(arguments["directory"])
        pattern = arguments["pattern"]
        results = []
        for p in directory.glob(pattern):
            if p.is_file():
                try:
                    img = Image.open(p)
                    results.append(_get_info(img, str(p)))
                except Exception as e:
                    results.append({"path": str(p), "error": str(e)})
        return [TextContent(type="text", text=json.dumps(results, indent=2))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationOptions(server_name="image-mcp", server_version="1.0.0"),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
