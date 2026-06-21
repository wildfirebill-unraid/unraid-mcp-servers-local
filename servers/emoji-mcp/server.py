import json
import random

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
import emoji


class EmojiServer(Server):
    VALID_CATEGORIES = ["Smileys & Emotion", "People & Body", "Animals & Nature",
                        "Food & Drink", "Travel & Places", "Activities",
                        "Objects", "Symbols", "Flags"]
    VALID_GROUPS = ["smileys", "animals", "food", "travel", "activities",
                    "objects", "symbols", "flags", "people"]

    def __init__(self):
        super().__init__("emoji")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="search_emoji", description="Search emoji by name or alias",
                 inputSchema={"type": "object", "properties": {
                     "query": {"type": "string", "description": "Search term to find emoji"}
                 }, "required": ["query"]}),
            Tool(name="emoji_info", description="Get metadata for an emoji character",
                 inputSchema={"type": "object", "properties": {
                     "emoji_char": {"type": "string", "description": "Single emoji character"}
                 }, "required": ["emoji_char"]}),
            Tool(name="encode_emoji", description="Convert emoji characters to :code: aliases",
                 inputSchema={"type": "object", "properties": {
                     "text": {"type": "string", "description": "Text containing emoji characters"}
                 }, "required": ["text"]}),
            Tool(name="decode_emoji", description="Convert :code: aliases to emoji characters",
                 inputSchema={"type": "object", "properties": {
                     "text": {"type": "string", "description": "Text containing :emoji: codes"}
                 }, "required": ["text"]}),
            Tool(name="list_category", description="List all emoji in a category",
                 inputSchema={"type": "object", "properties": {
                     "category": {"type": "string", "description": f"One of: {', '.join(VALID_CATEGORIES)}"}
                 }, "required": ["category"]}),
            Tool(name="list_group", description="List all emoji in a group",
                 inputSchema={"type": "object", "properties": {
                     "group": {"type": "string", "description": f"One of: {', '.join(VALID_GROUPS)}", "enum": VALID_GROUPS}
                 }, "required": ["group"]}),
            Tool(name="emoji_keywords", description="Get keywords/tags for an emoji",
                 inputSchema={"type": "object", "properties": {
                     "emoji_char": {"type": "string", "description": "Single emoji character"}
                 }, "required": ["emoji_char"]}),
            Tool(name="random_emoji", description="Get a random emoji character",
                 inputSchema={"type": "object", "properties": {}}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "search_emoji":
                query = args["query"].lower()
                results = []
                for emoji_char in emoji.EMOJI_DATA:
                    md = emoji.EMOJI_DATA[emoji_char]
                    tags = []
                    if isinstance(md, dict):
                        tags = md.get("alias", []) if isinstance(md.get("alias"), list) else [md.get("alias", "")]
                        tags = [t for t in tags if t]
                        tags = tags + [md.get("en", "")]
                    name_str = emoji.demojize(emoji_char).strip(":").replace("_", " ")
                    if query in name_str.lower() or any(query in t.lower() for t in tags if t):
                        results.append({"emoji": emoji_char, "name": name_str, "aliases": tags[:3]})
                    if len(results) >= 20:
                        break
                if not results:
                    for emoji_char in list(emoji.EMOJI_DATA.keys())[:50]:
                        md = emoji.EMOJI_DATA[emoji_char]
                        if isinstance(md, dict):
                            en = md.get("en", "")
                            if query in en.lower():
                                results.append({"emoji": emoji_char, "name": en})
                return [TextContent(type="text", text=json.dumps(results[:20], indent=2, ensure_ascii=False))]

            if name == "emoji_info":
                ec = args["emoji_char"]
                if ec not in emoji.EMOJI_DATA:
                    return [TextContent(type="text", text=json.dumps({"error": "Emoji not found"}, indent=2))]
                md = emoji.EMOJI_DATA[ec]
                info = {"emoji": ec}
                if isinstance(md, dict):
                    info["aliases"] = md.get("alias", [])
                    info["description"] = md.get("en", "")
                    info["tags"] = md.get("de", "")
                    info["version"] = md.get("E", "")
                    info["status"] = md.get("status", "")
                return [TextContent(type="text", text=json.dumps(info, indent=2, ensure_ascii=False))]

            if name == "encode_emoji":
                return [TextContent(type="text", text=emoji.demojize(args["text"]))]

            if name == "decode_emoji":
                return [TextContent(type="text", text=emoji.emojize(args["text"]))]

            if name == "list_category":
                cat = args["category"]
                results = []
                for emoji_char, md in emoji.EMOJI_DATA.items():
                    if isinstance(md, dict):
                        tags = [md.get("en", "").lower(), str(md.get("alias", "")).lower()]
                        if cat.lower() in " ".join(tags):
                            results.append({"emoji": emoji_char, "name": md.get("en", "")})
                    if len(results) >= 50:
                        break
                if not results:
                    for i, (ec, md) in enumerate(emoji.EMOJI_DATA.items()):
                        if i >= 50:
                            break
                        if isinstance(md, dict):
                            results.append({"emoji": ec, "name": md.get("en", "")})
                return [TextContent(type="text", text=json.dumps(results, indent=2, ensure_ascii=False))]

            if name == "list_group":
                group = args["group"].lower()
                group_map = {
                    "smileys": "smile", "animals": "animal", "food": "food",
                    "travel": "travel", "activities": "activity", "objects": "object",
                    "symbols": "symbol", "flags": "flag", "people": "people"
                }
                kw = group_map.get(group, group)
                results = []
                for emoji_char, md in emoji.EMOJI_DATA.items():
                    if isinstance(md, dict):
                        en = md.get("en", "").lower()
                        if kw in en:
                            results.append({"emoji": emoji_char, "name": md.get("en", "")})
                    if len(results) >= 50:
                        break
                return [TextContent(type="text", text=json.dumps(results, indent=2, ensure_ascii=False))]

            if name == "emoji_keywords":
                ec = args["emoji_char"]
                if ec not in emoji.EMOJI_DATA:
                    return [TextContent(type="text", text=json.dumps({"error": "Emoji not found"}, indent=2))]
                md = emoji.EMOJI_DATA[ec]
                keywords = []
                if isinstance(md, dict):
                    en = md.get("en", "")
                    aliases = md.get("alias", [])
                    if isinstance(aliases, list):
                        keywords.extend(aliases)
                    elif aliases:
                        keywords.append(aliases)
                    keywords.append(en)
                return [TextContent(type="text", text=json.dumps({"emoji": ec, "keywords": keywords}, indent=2, ensure_ascii=False))]

            if name == "random_emoji":
                ec = random.choice(list(emoji.EMOJI_DATA.keys()))
                return [TextContent(type="text", text=ec)]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = EmojiServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
