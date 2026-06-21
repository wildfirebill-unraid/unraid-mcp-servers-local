import json
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
from bs4 import BeautifulSoup


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


class HtmlServer(Server):
    def __init__(self):
        super().__init__("html")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="parse_html", description="Parse HTML and return structure summary (tag count, nesting depth)",
                 inputSchema={"type": "object", "properties": {
                     "html": {"type": "string", "description": "HTML content to parse"}
                 }, "required": ["html"]}),
            Tool(name="extract_links", description="Extract all links (href and text) from HTML",
                 inputSchema={"type": "object", "properties": {
                     "html": {"type": "string", "description": "HTML content"}
                 }, "required": ["html"]}),
            Tool(name="extract_text", description="Extract clean text from HTML (tags stripped, whitespace normalized)",
                 inputSchema={"type": "object", "properties": {
                     "html": {"type": "string", "description": "HTML content"}
                 }, "required": ["html"]}),
            Tool(name="query_tags", description="Query HTML by tag name with optional attribute filter",
                 inputSchema={"type": "object", "properties": {
                     "html": {"type": "string", "description": "HTML content"},
                     "tag": {"type": "string", "description": "Tag name to query (e.g. div, a, img)"},
                     "attributes": {"type": "string", "description": "Optional JSON object of attributes to filter (e.g. {\"class\": \"foo\"})"}
                 }, "required": ["html", "tag"]}),
            Tool(name="extract_tables", description="Extract HTML tables as JSON arrays",
                 inputSchema={"type": "object", "properties": {
                     "html": {"type": "string", "description": "HTML content"}
                 }, "required": ["html"]}),
            Tool(name="get_meta", description="Extract meta tags from HTML head",
                 inputSchema={"type": "object", "properties": {
                     "html": {"type": "string", "description": "HTML content"}
                 }, "required": ["html"]}),
            Tool(name="get_forms", description="Extract form fields from HTML (action, method, inputs)",
                 inputSchema={"type": "object", "properties": {
                     "html": {"type": "string", "description": "HTML content"}
                 }, "required": ["html"]}),
            Tool(name="html_to_text", description="Convert HTML to markdown-style plain text",
                 inputSchema={"type": "object", "properties": {
                     "html": {"type": "string", "description": "HTML content"}
                 }, "required": ["html"]}),
        ]

    def _parse_html(self, html: str) -> dict:
        soup = _soup(html)
        all_tags = [t.name for t in soup.find_all() if t.name]
        tag_counts = {}
        for t in all_tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
        return {
            "tag_count": len(all_tags),
            "tag_types": len(tag_counts),
            "tag_breakdown": tag_counts,
            "has_doctype": bool(soup.find(string=lambda s: isinstance(s, str) and s.strip().lower().startswith("<!doctype")) or any(isinstance(c, str) and c.strip().lower().startswith("<!doctype") for c in soup.contents)),
            "text_length": len(soup.get_text(strip=True)),
        }

    def _extract_links(self, html: str) -> list[dict]:
        soup = _soup(html)
        links = []
        for a in soup.find_all("a", href=True):
            links.append({"href": a["href"], "text": a.get_text(strip=True)})
        return links

    def _extract_tables(self, html: str) -> list[list[list[str]]]:
        soup = _soup(html)
        result = []
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = []
                for cell in tr.find_all(["td", "th"]):
                    cells.append(cell.get_text(strip=True))
                if cells:
                    rows.append(cells)
            if rows:
                result.append(rows)
        return result

    def _get_meta(self, html: str) -> dict:
        soup = _soup(html)
        metas = {}
        for m in soup.find_all("meta"):
            name = m.get("name") or m.get("property") or m.get("http-equiv") or ""
            content = m.get("content", "")
            if name:
                metas[name] = content
        title = soup.find("title")
        if title:
            metas["title"] = title.get_text(strip=True)
        return metas

    def _get_forms(self, html: str) -> list[dict]:
        soup = _soup(html)
        forms = []
        for form in soup.find_all("form"):
            fields = []
            for inp in form.find_all(["input", "textarea", "select"]):
                tag = inp.name
                name = inp.get("name", "")
                inp_type = inp.get("type", "text") if tag == "input" else tag
                if name:
                    fields.append({"name": name, "type": inp_type,
                                   "value": inp.get("value", "")})
            forms.append({
                "action": form.get("action", ""),
                "method": form.get("method", "get"),
                "fields": fields
            })
        return forms

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            html = args.get("html", "")

            if name == "parse_html":
                return [TextContent(type="text", text=json.dumps(self._parse_html(html)))]
            if name == "extract_links":
                return [TextContent(type="text", text=json.dumps(self._extract_links(html)))]
            if name == "extract_text":
                soup = _soup(html)
                return [TextContent(type="text", text=soup.get_text(separator=" ", strip=True))]
            if name == "query_tags":
                soup = _soup(html)
                tag = args["tag"]
                attrs = {}
                if args.get("attributes"):
                    attrs = json.loads(args["attributes"])
                elements = soup.find_all(tag, attrs) if attrs else soup.find_all(tag)
                result = []
                for el in elements:
                    result.append({"text": el.get_text(strip=True),
                                   "attrs": dict(el.attrs)})
                return [TextContent(type="text", text=json.dumps(result))]
            if name == "extract_tables":
                return [TextContent(type="text", text=json.dumps(self._extract_tables(html)))]
            if name == "get_meta":
                return [TextContent(type="text", text=json.dumps(self._get_meta(html)))]
            if name == "get_forms":
                return [TextContent(type="text", text=json.dumps(self._get_forms(html)))]
            if name == "html_to_text":
                soup = _soup(html)
                lines = []
                for el in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "tr"]):
                    text = el.get_text(strip=True)
                    if text:
                        if el.name == "li":
                            lines.append(f"- {text}")
                        elif el.name.startswith("h"):
                            prefix = "#" * int(el.name[1]) if el.name[1:].isdigit() else ""
                            lines.append(f"{prefix} {text}" if prefix else text)
                        elif el.name == "tr":
                            cells = [c.get_text(strip=True) for c in el.find_all(["td", "th"])]
                            lines.append(" | ".join(cells))
                        else:
                            lines.append(text)
                return [TextContent(type="text", text="\n".join(lines))]
            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = HtmlServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
