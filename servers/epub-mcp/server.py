import json
import os
import base64
from pathlib import Path

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
from ebooklib import epub


def _resolve_path(base: str, requested: str) -> str:
    p = (Path(base) / requested).resolve()
    if base:
        base_resolved = Path(base).resolve()
        if base_resolved not in p.parents and p != base_resolved:
            raise PermissionError(f"Access denied: {requested} is outside base path")
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    return str(p)


class EpubServer(Server):
    def __init__(self):
        super().__init__("epub")
        self._init_env()

    def _init_env(self):
        self._epub_path = os.environ.get("EPUB_PATH", "")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="read_metadata", description="Read EPUB metadata (title, author, publisher, language)",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to EPUB file"}
                 }, "required": ["path"]}),
            Tool(name="get_cover", description="Get cover image as base64",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to EPUB file"}
                 }, "required": ["path"]}),
            Tool(name="get_toc", description="Get table of contents",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to EPUB file"}
                 }, "required": ["path"]}),
            Tool(name="get_spine", description="Get spine (reading order) items",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to EPUB file"}
                 }, "required": ["path"]}),
            Tool(name="list_images", description="List embedded images with mime types",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to EPUB file"}
                 }, "required": ["path"]}),
            Tool(name="get_text_content", description="Extract full text content from all chapters",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to EPUB file"}
                 }, "required": ["path"]}),
            Tool(name="epub_info", description="Get comprehensive EPUB info",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to EPUB file"}
                 }, "required": ["path"]}),
            Tool(name="extract_chapter", description="Extract a specific chapter by index",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to EPUB file"},
                     "index": {"type": "integer", "description": "Chapter index (0-based)"}
                 }, "required": ["path", "index"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            path = None
            if name != "extract_chapter":
                path = _resolve_path(self._epub_path, args["path"])
            else:
                path = _resolve_path(self._epub_path, args.get("path", ""))

            book = epub.read_epub(path, {"ignore_ns": False})

            if name == "read_metadata":
                meta = {
                    "title": book.get_metadata("DC", "title"),
                    "creator": book.get_metadata("DC", "creator"),
                    "publisher": book.get_metadata("DC", "publisher"),
                    "language": book.get_metadata("DC", "language"),
                }
                out = {}
                for k, v in meta.items():
                    out[k] = [x[0] for x in v] if v else None
                return [TextContent(type="text", text=json.dumps(out))]

            if name == "get_cover":
                cover = book.get_metadata("OPF", "cover")
                if cover:
                    cover_id = cover[0][1].get("content", "")
                    item = book.get_item_with_id(cover_id)
                    if item:
                        data = base64.b64encode(item.get_content()).decode()
                        return [TextContent(type="text", text=json.dumps({
                            "mime": item.get_type(),
                            "data": data
                        }))]
                items = book.get_items_of_type(epub.EpubImage)
                for item in items:
                    if "cover" in item.file_name.lower():
                        data = base64.b64encode(item.get_content()).decode()
                        return [TextContent(type="text", text=json.dumps({
                            "mime": item.media_type,
                            "data": data
                        }))]
                return [TextContent(type="text", text=json.dumps({"cover": None}))]

            if name == "get_toc":
                toc = []
                for item in book.toc:
                    if isinstance(item, tuple) or isinstance(item, list):
                        href = item[0].href if hasattr(item[0], "href") else str(item[0])
                        title = item[0].title if hasattr(item[0], "title") else str(item[0])
                        toc.append({"title": title, "href": href})
                    else:
                        toc.append({"title": getattr(item, "title", str(item)),
                                    "href": getattr(item, "href", "")})
                return [TextContent(type="text", text=json.dumps(toc))]

            if name == "get_spine":
                spine = []
                for item in book.spine:
                    spine.append({"idref": item[0], "linear": item[1]})
                return [TextContent(type="text", text=json.dumps(spine))]

            if name == "list_images":
                images = []
                for item in book.get_items_of_type(epub.EpubImage):
                    images.append({"file_name": item.file_name, "mime": item.media_type,
                                   "size": len(item.get_content())})
                return [TextContent(type="text", text=json.dumps(images))]

            if name == "get_text_content":
                texts = []
                for item in book.get_items_of_type(epub.EpubText):
                    texts.append({"file_name": item.file_name, "content": item.get_content().decode("utf-8", errors="replace")})
                return [TextContent(type="text", text=json.dumps(texts))]

            if name == "epub_info":
                meta = {"title": None, "creator": None, "publisher": None, "language": None}
                for k in meta:
                    v = book.get_metadata("DC", k)
                    meta[k] = [x[0] for x in v] if v else None
                toc_count = len(book.toc)
                spine_count = len(book.spine)
                img_count = len(list(book.get_items_of_type(epub.EpubImage)))
                text_count = len(list(book.get_items_of_type(epub.EpubText)))
                return [TextContent(type="text", text=json.dumps({
                    "metadata": meta, "toc_items": toc_count,
                    "spine_items": spine_count, "images": img_count,
                    "text_items": text_count
                }))]

            if name == "extract_chapter":
                idx = args.get("index", 0)
                texts = list(book.get_items_of_type(epub.EpubText))
                if idx < 0 or idx >= len(texts):
                    return [TextContent(type="text", text=json.dumps({"error": f"Index {idx} out of range (0-{len(texts)-1})"}))]
                item = texts[idx]
                return [TextContent(type="text", text=json.dumps({
                    "file_name": item.file_name,
                    "content": item.get_content().decode("utf-8", errors="replace")
                }))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = EpubServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
