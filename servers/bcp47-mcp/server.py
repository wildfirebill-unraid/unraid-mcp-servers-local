import json
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

import bcp47


def _serialize(obj: Any) -> Any:
    if hasattr(obj, "_asdict"):
        return {k: _serialize(v) for k, v in obj._asdict().items() if v}
    if hasattr(obj, "__dict__"):
        return {k: _serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_") and v}
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(i) for i in obj]
    if isinstance(obj, set):
        return sorted(obj)
    return str(obj) if not isinstance(obj, (str, int, float, bool, type(None))) else obj


class Bcp47Server(Server):
    def __init__(self):
        super().__init__("bcp47")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="validate_tag",
                description="Validate a BCP47 language tag",
                inputSchema={
                    "type": "object",
                    "properties": {"tag": {"type": "string", "description": "BCP47 language tag to validate"}},
                    "required": ["tag"],
                },
            ),
            Tool(
                name="parse_tag",
                description="Parse a BCP47 tag into its components (language, script, region, variants, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {"tag": {"type": "string", "description": "BCP47 language tag to parse"}},
                    "required": ["tag"],
                },
            ),
            Tool(
                name="format_tag",
                description="Build a BCP47 tag from component parts",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "language": {"type": "string", "description": "Language subtag (e.g. 'en')"},
                        "script": {"type": "string", "description": "Script subtag (e.g. 'Latn')"},
                        "region": {"type": "string", "description": "Region subtag (e.g. 'US')"},
                        "variant": {"type": "string", "description": "Variant subtag (e.g. 'valencia')"},
                        "extension": {"type": "string", "description": "Extension subtag"},
                        "privateuse": {"type": "string", "description": "Private-use subtag"},
                    },
                },
            ),
            Tool(
                name="search_by_name",
                description="Search for a language by its name",
                inputSchema={
                    "type": "object",
                    "properties": {"name": {"type": "string", "description": "Language name to search for"}},
                    "required": ["name"],
                },
            ),
            Tool(
                name="list_all_tags",
                description="List all known BCP47 language tags",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="tag_info",
                description="Get full information about a BCP47 tag including language, script, and region details",
                inputSchema={
                    "type": "object",
                    "properties": {"tag": {"type": "string", "description": "BCP47 language tag"}},
                    "required": ["tag"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}

        try:
            if name == "validate_tag":
                tag_str = args.get("tag", "")
                try:
                    parsed = bcp47.tag(tag_str)
                    return [TextContent(type="text", text=json.dumps({"valid": True, "tag": tag_str}))]
                except (ValueError, TypeError):
                    return [TextContent(type="text", text=json.dumps({"valid": False, "tag": tag_str}))]

            elif name == "parse_tag":
                tag_str = args.get("tag", "")
                try:
                    parsed = bcp47.tag(tag_str)
                    components = {}
                    for field in ("language", "script", "region", "variant", "extension", "privateuse", "extlang", "grandfathered", "redundant", "prefix"):
                        val = getattr(parsed, field, None)
                        if val:
                            components[field] = str(val)
                    return [TextContent(type="text", text=json.dumps({"tag": tag_str, "components": components}))]
                except (ValueError, TypeError) as e:
                    return [TextContent(type="text", text=json.dumps({"error": f"Invalid tag: {e}"}))]

            elif name == "format_tag":
                parts = []
                if args.get("language"):
                    parts.append(args["language"])
                if args.get("script"):
                    parts.append(args["script"])
                if args.get("region"):
                    parts.append(args["region"])
                if args.get("variant"):
                    parts.append(args["variant"])
                if args.get("extension"):
                    parts.append(args["extension"])
                if args.get("privateuse"):
                    parts.append(f"x-{args['privateuse']}")
                tag_str = "-".join(parts)
                try:
                    bcp47.tag(tag_str)
                    return [TextContent(type="text", text=json.dumps({"tag": tag_str, "valid": True}))]
                except (ValueError, TypeError):
                    return [TextContent(type="text", text=json.dumps({"tag": tag_str, "valid": False, "warning": "Constructed tag did not validate"}))]

            elif name == "search_by_name":
                query = args.get("name", "").lower()
                results = []
                for lang in bcp47.languages():
                    names = lang.get("names", [])
                    if any(query in n.lower() for n in names):
                        results.append({"code": lang.get("code"), "names": names})
                return [TextContent(type="text", text=json.dumps({"query": args.get("name"), "results": results}))]

            elif name == "list_all_tags":
                tags = sorted(bcp47.langtags())
                return [TextContent(type="text", text=json.dumps({"count": len(tags), "tags": tags}))]

            elif name == "tag_info":
                tag_str = args.get("tag", "")
                try:
                    parsed = bcp47.tag(tag_str)
                    info = _serialize(parsed)
                    lang_code = getattr(parsed, "language", None)
                    script_code = getattr(parsed, "script", None)
                    region_code = getattr(parsed, "region", None)
                    if lang_code:
                        for lang in bcp47.languages():
                            if lang.get("code") == lang_code:
                                info["language_name"] = lang.get("names", [])
                                break
                    if script_code:
                        for sc in bcp47.scripts():
                            if sc.get("code") == script_code:
                                info["script_name"] = sc.get("name")
                                break
                    if region_code:
                        for rg in bcp47.regions():
                            if rg.get("code") == region_code:
                                info["region_name"] = rg.get("name")
                                break
                    return [TextContent(type="text", text=json.dumps({"tag": tag_str, "info": info}))]
                except (ValueError, TypeError) as e:
                    return [TextContent(type="text", text=json.dumps({"error": f"Invalid tag: {e}"}))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = Bcp47Server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
