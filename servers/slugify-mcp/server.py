import json
import re
import unicodedata
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class SlugifyServer(Server):
    def __init__(self):
        super().__init__("slugify")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="slugify", description="Convert text to a URL-safe slug",
                 inputSchema={"type": "object", "properties": {
                     "text": {"type": "string", "description": "Text to slugify"},
                     "separator": {"type": "string", "description": "Separator char (default '-')"},
                     "max_length": {"type": "integer", "description": "Max slug length (default 0 = no limit)"}},
                     "required": ["text"]}),
            Tool(name="slugify_multiline", description="Convert each line of text to a slug",
                 inputSchema={"type": "object", "properties": {
                     "text": {"type": "string", "description": "Multi-line text"},
                     "separator": {"type": "string", "description": "Separator char (default '-')"}},
                     "required": ["text"]}),
            Tool(name="transliterate", description="Transliterate unicode text to ASCII",
                 inputSchema={"type": "object", "properties": {
                     "text": {"type": "string", "description": "Text to transliterate"}},
                     "required": ["text"]}),
            Tool(name="slug_unique", description="Ensure slug is unique against a list",
                 inputSchema={"type": "object", "properties": {
                     "text": {"type": "string", "description": "Text to slugify"},
                     "existing_slugs": {"type": "array", "items": {"type": "string"},
                                        "description": "List of existing slugs"}},
                     "required": ["text", "existing_slugs"]}),
            Tool(name="slug_clean", description="Clean up an existing slug",
                 inputSchema={"type": "object", "properties": {
                     "slug": {"type": "string", "description": "Slug to clean"}},
                     "required": ["slug"]}),
            Tool(name="suggest_slug", description="Suggest a slug from a title",
                 inputSchema={"type": "object", "properties": {
                     "title": {"type": "string", "description": "Title"},
                     "existing_slugs": {"type": "array", "items": {"type": "string"},
                                        "description": "Existing slugs to avoid"}},
                     "required": ["title"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "slugify":
                result = self._slugify(args)
            elif name == "slugify_multiline":
                result = self._slugify_multiline(args)
            elif name == "transliterate":
                result = self._transliterate(args)
            elif name == "slug_unique":
                result = self._slug_unique(args)
            elif name == "slug_clean":
                result = self._slug_clean(args)
            elif name == "suggest_slug":
                result = self._suggest_slug(args)
            else:
                raise ValueError(f"Unknown tool: {name}")
            return [TextContent(type="text", text=json.dumps(result))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    def _do_slugify(self, text: str, separator: str = "-") -> str:
        nfkd = unicodedata.normalize("NFKD", text)
        ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
        ascii_str = ascii_str.lower().strip()
        ascii_str = re.sub(r"[^a-z0-9\s_-]", "", ascii_str)
        ascii_str = re.sub(r"[\s_]+", separator, ascii_str)
        ascii_str = re.sub(rf"{re.escape(separator)}+", separator, ascii_str)
        ascii_str = ascii_str.strip(separator)
        return ascii_str

    def _slugify(self, args: dict) -> dict:
        text = args["text"]
        sep = args.get("separator", "-")
        max_len = args.get("max_length", 0)
        slug = self._do_slugify(text, sep)
        if max_len > 0 and len(slug) > max_len:
            slug = slug[:max_len].rstrip(sep)
        return {"slug": slug}

    def _slugify_multiline(self, args: dict) -> dict:
        text = args["text"]
        sep = args.get("separator", "-")
        lines = [self._do_slugify(line, sep) for line in text.splitlines() if line.strip()]
        return {"slugs": lines}

    def _transliterate(self, args: dict) -> dict:
        text = args["text"]
        nfkd = unicodedata.normalize("NFKD", text)
        ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
        return {"transliterated": ascii_str}

    def _slug_unique(self, args: dict) -> dict:
        text = args["text"]
        existing = set(args.get("existing_slugs", []))
        slug = self._do_slugify(text)
        original = slug
        counter = 1
        while slug in existing:
            slug = f"{original}-{counter}"
            counter += 1
        return {"slug": slug}

    def _slug_clean(self, args: dict) -> dict:
        slug = args["slug"].lower().strip()
        slug = re.sub(r"[^a-z0-9_-]", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")
        return {"slug": slug}

    def _suggest_slug(self, args: dict) -> dict:
        title = args["title"]
        existing = set(args.get("existing_slugs", []))
        slug = self._do_slugify(title)
        original = slug
        counter = 1
        while slug in existing:
            slug = f"{original}-{counter}"
            counter += 1
        return {"suggested": slug}

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = SlugifyServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
