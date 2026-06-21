import json
import gzip
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
from pathlib import Path
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
MAX_URLS = 50000
MAX_SIZE = 50 * 1024 * 1024

class SitemapServer(Server):
    def __init__(self):
        super().__init__("sitemap")

    def _load_sitemap(self, path_or_url: str) -> bytes:
        p = Path(path_or_url)
        if p.exists():
            raw = p.read_bytes()
        else:
            import urllib.request
            with urllib.request.urlopen(path_or_url, timeout=30) as resp:
                raw = resp.read()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return raw

    def _parse_sitemap_bytes(self, raw: bytes) -> list[dict[str, Any]]:
        root = ET.fromstring(raw)
        ns = self._detect_ns(root.tag)
        urls = []
        for url_elem in root.findall(f"{ns}url"):
            loc = url_elem.findtext(f"{ns}loc", "").strip()
            if not loc:
                continue
            entry = {"loc": loc}
            lastmod = url_elem.findtext(f"{ns}lastmod", "").strip()
            if lastmod:
                entry["lastmod"] = lastmod
            changefreq = url_elem.findtext(f"{ns}changefreq", "").strip()
            if changefreq:
                entry["changefreq"] = changefreq
            priority = url_elem.findtext(f"{ns}priority", "").strip()
            if priority:
                entry["priority"] = priority
            urls.append(entry)
        return urls

    def _detect_ns(self, tag: str) -> str:
        idx = tag.find("}")
        if idx != -1:
            return tag[: idx + 1]
        return ""

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="parse_sitemap", description="Parse a sitemap XML file or URL into structured URL entries with metadata", inputSchema={"type": "object", "properties": {"path_or_url": {"type": "string", "description": "Local file path or URL to the sitemap XML"}}, "required": ["path_or_url"]}),
            Tool(name="generate_sitemap", description="Generate a sitemap XML string from a list of URLs", inputSchema={"type": "object", "properties": {"urls": {"type": "array", "items": {"type": "string"}, "description": "List of URLs to include"}, "changefreq": {"type": "string", "description": "Optional change frequency (always, hourly, daily, weekly, monthly, yearly, never)", "default": ""}, "priority": {"type": "number", "description": "Optional priority (0.0 to 1.0)", "default": 0.5}}, "required": ["urls"]}),
            Tool(name="validate_sitemap", description="Validate a sitemap XML file for well-formedness, URL count limit (50k), and size limit (50MB)", inputSchema={"type": "object", "properties": {"path": {"type": "string", "description": "Local file path to the sitemap XML"}}, "required": ["path"]}),
            Tool(name="sitemap_index", description="Generate a sitemap index XML from multiple sitemap URLs", inputSchema={"type": "object", "properties": {"sitemaps": {"type": "array", "items": {"type": "string"}, "description": "List of sitemap URLs to include in the index"}}, "required": ["sitemaps"]}),
            Tool(name="sitemap_analyze", description="Analyze a sitemap and return statistics: total URLs, unique domains, and URL metadata", inputSchema={"type": "object", "properties": {"path_or_url": {"type": "string", "description": "Local file path or URL to the sitemap XML"}}, "required": ["path_or_url"]}),
            Tool(name="merge_sitemaps", description="Merge multiple sitemap files into a single sitemap XML", inputSchema={"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}, "description": "List of local file paths to sitemap XML files"}}, "required": ["paths"]}),
            Tool(name="extract_urls", description="Extract just the URL strings from a sitemap as a JSON list", inputSchema={"type": "object", "properties": {"path_or_url": {"type": "string", "description": "Local file path or URL to the sitemap XML"}}, "required": ["path_or_url"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "parse_sitemap":
                raw = self._load_sitemap(args["path_or_url"])
                urls = self._parse_sitemap_bytes(raw)
                return [TextContent(type="text", text=json.dumps(urls, indent=2))]

            elif name == "generate_sitemap":
                urls = args["urls"]
                cf = args.get("changefreq", "")
                pr = args.get("priority", "")
                ns = SITEMAP_NS
                root = ET.Element(f"{{{ns}}}urlset")
                for u in urls:
                    ue = ET.SubElement(root, f"{{{ns}}}url")
                    loc = ET.SubElement(ue, f"{{{ns}}}loc")
                    loc.text = u
                    if cf:
                        e = ET.SubElement(ue, f"{{{ns}}}changefreq")
                        e.text = cf
                    if pr:
                        e = ET.SubElement(ue, f"{{{ns}}}priority")
                        e.text = str(pr)
                xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)
                return [TextContent(type="text", text=xml_str)]

            elif name == "validate_sitemap":
                p = Path(args["path"])
                if not p.exists():
                    raise FileNotFoundError(f"File not found: {args['path']}")
                size = p.stat().st_size
                issues = []
                if size > MAX_SIZE:
                    issues.append(f"File size {size} bytes exceeds 50MB limit")
                raw = p.read_bytes()
                if raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                try:
                    urls = self._parse_sitemap_bytes(raw)
                except ET.ParseError as e:
                    issues.append(f"XML parse error: {e}")
                    return [TextContent(type="text", text=json.dumps({"valid": False, "issues": issues}))]
                if len(urls) > MAX_URLS:
                    issues.append(f"URL count {len(urls)} exceeds 50,000 limit")
                return [TextContent(type="text", text=json.dumps({"valid": len(issues) == 0, "url_count": len(urls), "size_bytes": size, "issues": issues}))]

            elif name == "sitemap_index":
                sitemaps = args["sitemaps"]
                ns = SITEMAP_NS
                root = ET.Element(f"{{{ns}}}sitemapindex")
                for s in sitemaps:
                    se = ET.SubElement(root, f"{{{ns}}}sitemap")
                    loc = ET.SubElement(se, f"{{{ns}}}loc")
                    loc.text = s
                xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)
                return [TextContent(type="text", text=xml_str)]

            elif name == "sitemap_analyze":
                raw = self._load_sitemap(args["path_or_url"])
                urls = self._parse_sitemap_bytes(raw)
                domains = set()
                for u in urls:
                    parsed = urlparse(u["loc"])
                    if parsed.netloc:
                        domains.add(parsed.netloc)
                result = {
                    "total_urls": len(urls),
                    "unique_domains": list(sorted(domains)),
                    "domain_count": len(domains),
                    "sample_urls": [u["loc"] for u in urls[:10]],
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "merge_sitemaps":
                all_urls = []
                for fp in args["paths"]:
                    raw = self._load_sitemap(fp)
                    all_urls.extend(self._parse_sitemap_bytes(raw))
                ns = SITEMAP_NS
                root = ET.Element(f"{{{ns}}}urlset")
                for u in all_urls:
                    ue = ET.SubElement(root, f"{{{ns}}}url")
                    loc = ET.SubElement(ue, f"{{{ns}}}loc")
                    loc.text = u["loc"]
                    if "lastmod" in u:
                        e = ET.SubElement(ue, f"{{{ns}}}lastmod")
                        e.text = u["lastmod"]
                    if "changefreq" in u:
                        e = ET.SubElement(ue, f"{{{ns}}}changefreq")
                        e.text = u["changefreq"]
                    if "priority" in u:
                        e = ET.SubElement(ue, f"{{{ns}}}priority")
                        e.text = u["priority"]
                xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)
                return [TextContent(type="text", text=xml_str)]

            elif name == "extract_urls":
                raw = self._load_sitemap(args["path_or_url"])
                urls = self._parse_sitemap_bytes(raw)
                return [TextContent(type="text", text=json.dumps([u["loc"] for u in urls], indent=2))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    server = SitemapServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
