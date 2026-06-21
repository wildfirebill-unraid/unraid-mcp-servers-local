import json
import os
from pathlib import Path

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
import fitz


def _resolve_path(base: str, requested: str) -> str:
    p = (Path(base) / requested).resolve()
    if base:
        base_resolved = Path(base).resolve()
        if base_resolved not in p.parents and p != base_resolved:
            raise PermissionError(f"Access denied: {requested} is outside base path")
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    return str(p)


class PdfServer(Server):
    def __init__(self):
        super().__init__("pdf")
        self._init_env()

    def _init_env(self):
        self._pdf_path = os.environ.get("PDF_PATH", "")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="extract_text", description="Extract all text from PDF",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to PDF file"}
                 }, "required": ["path"]}),
            Tool(name="read_metadata", description="Read PDF metadata (title, author, subject, producer)",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to PDF file"}
                 }, "required": ["path"]}),
            Tool(name="page_info", description="Get page count and page dimensions",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to PDF file"}
                 }, "required": ["path"]}),
            Tool(name="list_pages", description="Extract text from specific pages (comma-separated)",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to PDF file"},
                     "page_numbers": {"type": "string", "description": "Comma-separated page numbers (1-indexed)"}
                 }, "required": ["path", "page_numbers"]}),
            Tool(name="count_pages", description="Get total page count",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to PDF file"}
                 }, "required": ["path"]}),
            Tool(name="extract_images", description="List embedded images with metadata",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to PDF file"}
                 }, "required": ["path"]}),
            Tool(name="pdf_info", description="Get comprehensive PDF info",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to PDF file"}
                 }, "required": ["path"]}),
            Tool(name="search_text", description="Search for text in PDF, return locations",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Path to PDF file"},
                     "query": {"type": "string", "description": "Text to search for"}
                 }, "required": ["path", "query"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            path = _resolve_path(self._pdf_path, args["path"])
            doc = fitz.open(path)

            if name == "extract_text":
                text = "".join(page.get_text() for page in doc)
                doc.close()
                return [TextContent(type="text", text=text)]

            if name == "read_metadata":
                meta = doc.metadata
                doc.close()
                return [TextContent(type="text", text=json.dumps(meta))]

            if name == "page_info":
                pages = []
                for i, page in enumerate(doc):
                    r = page.rect
                    pages.append({"page": i + 1, "width": r.width, "height": r.height})
                doc.close()
                return [TextContent(type="text", text=json.dumps({"count": len(pages), "pages": pages}))]

            if name == "list_pages":
                numbers = [int(x.strip()) for x in args["page_numbers"].split(",")]
                results = {}
                for n in numbers:
                    if 1 <= n <= len(doc):
                        results[n] = doc[n - 1].get_text()
                    else:
                        results[n] = f"Page {n} out of range (1-{len(doc)})"
                doc.close()
                return [TextContent(type="text", text=json.dumps(results))]

            if name == "count_pages":
                count = len(doc)
                doc.close()
                return [TextContent(type="text", text=json.dumps({"count": count}))]

            if name == "extract_images":
                images = []
                for i, page in enumerate(doc):
                    for img in page.get_images():
                        xref = img[0]
                        base = doc.extract_image(xref)
                        images.append({
                            "page": i + 1, "xref": xref,
                            "width": base.get("width"), "height": base.get("height"),
                            "ext": base.get("ext"), "size": len(base.get("image", b""))
                        })
                doc.close()
                return [TextContent(type="text", text=json.dumps(images))]

            if name == "pdf_info":
                meta = doc.metadata
                page_count = len(doc)
                pages = []
                for i, page in enumerate(doc):
                    r = page.rect
                    pages.append({"page": i + 1, "width": r.width, "height": r.height})
                img_count = sum(len(page.get_images()) for page in doc)
                doc.close()
                return [TextContent(type="text", text=json.dumps({
                    "metadata": meta, "page_count": page_count,
                    "pages": pages, "image_count": img_count
                }))]

            if name == "search_text":
                query = args["query"]
                results = []
                for i, page in enumerate(doc):
                    instances = page.search_for(query)
                    for inst in instances:
                        results.append({
                            "page": i + 1,
                            "x0": inst.x0, "y0": inst.y0,
                            "x1": inst.x1, "y1": inst.y1
                        })
                doc.close()
                return [TextContent(type="text", text=json.dumps({
                    "query": query, "matches": len(results), "locations": results
                }))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = PdfServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
