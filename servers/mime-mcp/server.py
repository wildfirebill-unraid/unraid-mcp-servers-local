import json
import mimetypes
from pathlib import Path

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


_CATEGORY_MAP: dict[str, list[str]] = {
    "text": [
        "text/plain", "text/html", "text/css", "text/javascript", "text/csv",
        "text/xml", "text/markdown", "text/yaml", "text/json",
    ],
    "image": [
        "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
        "image/bmp", "image/tiff", "image/avif", "image/heic", "image/x-icon",
    ],
    "audio": [
        "audio/mpeg", "audio/wav", "audio/ogg", "audio/flac", "audio/aac",
        "audio/webm", "audio/mp4", "audio/x-wav",
    ],
    "video": [
        "video/mp4", "video/webm", "video/ogg", "video/x-msvideo",
        "video/quicktime", "video/x-matroska", "video/mpeg",
    ],
    "application": [
        "application/json", "application/pdf", "application/zip", "application/gzip",
        "application/xml", "application/octet-stream", "application/x-tar",
        "application/x-rar-compressed", "application/x-7z-compressed",
        "application/rtf", "application/wasm", "application/x-shockwave-flash",
    ],
}


_MAGIC_BYTES: dict[str, list[dict[str, str]]] = {
    "image/jpeg": [{"offset": 0, "bytes": "FF D8 FF"}],
    "image/png": [{"offset": 0, "bytes": "89 50 4E 47"}],
    "image/gif": [{"offset": 0, "bytes": "47 49 46 38"}],
    "image/webp": [{"offset": 8, "bytes": "57 45 42 50"}],
    "image/bmp": [{"offset": 0, "bytes": "42 4D"}],
    "image/tiff": [{"offset": 0, "bytes": "49 49 2A 00"}, {"offset": 0, "bytes": "4D 4D 00 2A"}],
    "application/pdf": [{"offset": 0, "bytes": "25 50 44 46"}],
    "application/zip": [{"offset": 0, "bytes": "50 4B 03 04"}],
    "application/gzip": [{"offset": 0, "bytes": "1F 8B"}],
    "application/x-tar": [{"offset": 257, "bytes": "75 73 74 61 72"}],
    "audio/mpeg": [{"offset": 0, "bytes": "49 44 33"}],
    "audio/flac": [{"offset": 0, "bytes": "66 4C 61 43"}],
    "audio/wav": [{"offset": 0, "bytes": "52 49 46 46"}],
    "video/webm": [{"offset": 0, "bytes": "1A 45 DF A3"}],
    "video/x-matroska": [{"offset": 0, "bytes": "1A 45 DF A3"}],
}


def _mime_category(mime: str) -> str:
    cat = mime.split("/")[0]
    if cat in ("text", "image", "audio", "video", "application"):
        return cat
    if mime == "message/rfc822":
        return "message"
    if mime.startswith("multipart/"):
        return "multipart"
    if mime.startswith("model/"):
        return "model"
    if mime.startswith("font/"):
        return "font"
    return "other"


def _guess_extensions() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for ext, mime in mimetypes.types_map.items():
        result.setdefault(mime, []).append(ext)
    return result


def _common_ext_for_mime(mime: str) -> list[str]:
    return _guess_extensions().get(mime, [])


class MimeServer(Server):
    def __init__(self):
        super().__init__("mime")
        mimetypes.init()
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="detect_mime", description="Detect MIME type of a file by its extension", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "File path to detect MIME type for"}}, "required": ["path"]}),
            Tool(name="extension_to_mime", description="Look up the MIME type for a file extension", inputSchema={"type": "object", "properties": {"ext": {"type": "string", "description": "File extension (e.g. .html, .jpg, .pdf)"}}, "required": ["ext"]}),
            Tool(name="mime_to_extension", description="Look up common file extensions for a MIME type", inputSchema={"type": "object", "properties": {"mime": {"type": "string", "description": "MIME type (e.g. text/html, image/jpeg)"}}, "required": ["mime"]}),
            Tool(name="mime_info", description="Get detailed info about a MIME type: category, type, and common extensions", inputSchema={"type": "object", "properties": {"mime": {"type": "string", "description": "MIME type (e.g. text/html, image/jpeg)"}}, "required": ["mime"]}),
            Tool(name="magic_bytes", description="Return known magic byte signatures for a MIME type", inputSchema={"type": "object", "properties": {"mime": {"type": "string", "description": "MIME type (e.g. image/jpeg, application/pdf)"}}, "required": ["mime"]}),
            Tool(name="mime_category", description="Classify a MIME type into a category (text/image/audio/video/application)", inputSchema={"type": "object", "properties": {"mime": {"type": "string", "description": "MIME type to classify"}}, "required": ["mime"]}),
            Tool(name="common_types", description="List common MIME types in a category", inputSchema={"type": "object", "properties": {"category": {"type": "string", "description": "Category: text, image, audio, video, or application", "enum": ["text", "image", "audio", "video", "application"]}}, "required": ["category"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "detect_mime":
                p = Path(args["path"])
                ext = p.suffix.lower()
                mime, _ = mimetypes.guess_type(str(p))
                return [TextContent(type="text", text=json.dumps({"path": args["path"], "extension": ext, "mime_type": mime or "application/octet-stream"}))]
            elif name == "extension_to_mime":
                ext = args["ext"].lower() if args["ext"].startswith(".") else "." + args["ext"].lower()
                mime = mimetypes.types_map.get(ext)
                if not mime:
                    return [TextContent(type="text", text=json.dumps({"error": f"No MIME type found for extension '{args['ext']}'"}))]
                return [TextContent(type="text", text=json.dumps({"extension": args["ext"], "mime_type": mime}))]
            elif name == "mime_to_extension":
                mime = args["mime"].lower()
                extensions = _common_ext_for_mime(mime)
                if not extensions:
                    return [TextContent(type="text", text=json.dumps({"error": f"No extensions found for MIME type '{args['mime']}'"}))]
                return [TextContent(type="text", text=json.dumps({"mime_type": mime, "extensions": extensions}))]
            elif name == "mime_info":
                mime = args["mime"].lower()
                cat = _mime_category(mime)
                extensions = _common_ext_for_mime(mime)
                return [TextContent(type="text", text=json.dumps({"mime_type": mime, "category": cat, "type_part": mime.split("/")[1], "common_extensions": extensions}))]
            elif name == "magic_bytes":
                mime = args["mime"].lower()
                sigs = _MAGIC_BYTES.get(mime)
                if not sigs:
                    return [TextContent(type="text", text=json.dumps({"mime_type": mime, "magic_bytes": [], "note": "No magic byte signatures known for this type"}))]
                return [TextContent(type="text", text=json.dumps({"mime_type": mime, "magic_bytes": sigs}))]
            elif name == "mime_category":
                mime = args["mime"].lower()
                cat = _mime_category(mime)
                return [TextContent(type="text", text=json.dumps({"mime_type": mime, "category": cat}))]
            elif name == "common_types":
                cat = args["category"].lower()
                types = _CATEGORY_MAP.get(cat, [])
                return [TextContent(type="text", text=json.dumps({"category": cat, "common_types": types}))]
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = MimeServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
