import json
import feedparser
from email.utils import parsedate_to_datetime
from datetime import datetime
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


def _parse_date(date_str: str) -> datetime | None:
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        pass
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return None


class RssServer(Server):
    def __init__(self):
        super().__init__("rss-server")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="fetch_feed",
                description="Fetch and parse an RSS/Atom feed URL",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Feed URL to fetch"}
                    },
                    "required": ["url"],
                },
            ),
            Tool(
                name="list_entries",
                description="List entries from a feed with title, link, and published date",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Feed URL"},
                        "limit": {
                            "type": "integer",
                            "description": "Max entries to return (default 20)",
                            "default": 20,
                        },
                    },
                    "required": ["url"],
                },
            ),
            Tool(
                name="search_entries",
                description="Search feed entries by keyword in title or summary",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Feed URL"},
                        "query": {
                            "type": "string",
                            "description": "Search keyword",
                        },
                    },
                    "required": ["url", "query"],
                },
            ),
            Tool(
                name="filter_by_date",
                description="Filter feed entries published since a given date",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Feed URL"},
                        "since": {
                            "type": "string",
                            "description": "ISO date string (e.g. 2024-01-01 or 2024-01-01T00:00:00)",
                        },
                    },
                    "required": ["url", "since"],
                },
            ),
            Tool(
                name="feed_info",
                description="Get feed-level metadata (title, link, description, language)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Feed URL"}
                    },
                    "required": ["url"],
                },
            ),
            Tool(
                name="get_entry",
                description="Get full details of a specific feed entry by its id or link",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Feed URL"},
                        "entry_id": {
                            "type": "string",
                            "description": "Entry id or link to look up",
                        },
                    },
                    "required": ["url", "entry_id"],
                },
            ),
            Tool(
                name="feed_to_json",
                description="Convert an entire feed to a JSON representation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Feed URL"}
                    },
                    "required": ["url"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "fetch_feed":
            return await self._fetch_feed(args["url"])
        if name == "list_entries":
            return await self._list_entries(args["url"], args.get("limit", 20))
        if name == "search_entries":
            return await self._search_entries(args["url"], args["query"])
        if name == "filter_by_date":
            return await self._filter_by_date(args["url"], args["since"])
        if name == "feed_info":
            return await self._feed_info(args["url"])
        if name == "get_entry":
            return await self._get_entry(args["url"], args["entry_id"])
        if name == "feed_to_json":
            return await self._feed_to_json(args["url"])
        raise ValueError(f"Unknown tool: {name}")

    def _parse(self, url: str) -> feedparser.FeedParserDict:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            raise RuntimeError(f"Failed to parse feed: {feed.bozo_exception}")
        return feed

    async def _fetch_feed(self, url: str) -> list[TextContent]:
        feed = self._parse(url)
        result = {
            "status": "ok",
            "entries_count": len(feed.entries),
            "feed_title": feed.feed.get("title", ""),
            "feed_link": feed.feed.get("link", ""),
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _list_entries(self, url: str, limit: int) -> list[TextContent]:
        feed = self._parse(url)
        entries = []
        for entry in feed.entries[:limit]:
            entries.append(
                {
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "id": entry.get("id", entry.get("link", "")),
                }
            )
        return [TextContent(type="text", text=json.dumps(entries, indent=2))]

    async def _search_entries(self, url: str, query: str) -> list[TextContent]:
        feed = self._parse(url)
        q = query.lower()
        results = []
        for entry in feed.entries:
            title = entry.get("title", "").lower()
            summary = entry.get("summary", entry.get("description", "")).lower()
            if q in title or q in summary:
                results.append(
                    {
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "id": entry.get("id", entry.get("link", "")),
                    }
                )
        return [TextContent(type="text", text=json.dumps({"query": query, "count": len(results), "results": results}, indent=2))]

    async def _filter_by_date(self, url: str, since: str) -> list[TextContent]:
        since_dt = _parse_date(since)
        if since_dt is None:
            return [TextContent(type="text", text=json.dumps({"error": f"Invalid date: {since}"}))]
        feed = self._parse(url)
        results = []
        for entry in feed.entries:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published is None:
                continue
            dt = datetime(*published[:6])
            if dt >= since_dt:
                results.append(
                    {
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "id": entry.get("id", entry.get("link", "")),
                    }
                )
        return [TextContent(type="text", text=json.dumps({"since": since, "count": len(results), "results": results}, indent=2))]

    async def _feed_info(self, url: str) -> list[TextContent]:
        feed = self._parse(url)
        info = {
            "title": feed.feed.get("title", ""),
            "link": feed.feed.get("link", ""),
            "description": feed.feed.get("description", feed.feed.get("subtitle", "")),
            "language": feed.feed.get("language", ""),
            "author": feed.feed.get("author", ""),
            "entries_count": len(feed.entries),
            "feed_type": "Atom" if feed.get("version", "").startswith("atom") else "RSS",
        }
        return [TextContent(type="text", text=json.dumps(info, indent=2))]

    async def _get_entry(self, url: str, entry_id: str) -> list[TextContent]:
        feed = self._parse(url)
        for entry in feed.entries:
            eid = entry.get("id", "") or entry.get("link", "")
            elink = entry.get("link", "") or ""
            if entry_id in (eid, elink):
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "title": entry.get("title", ""),
                                "link": entry.get("link", ""),
                                "published": entry.get("published", ""),
                                "id": entry.get("id", ""),
                                "summary": entry.get("summary", ""),
                                "author": entry.get("author", ""),
                                "tags": [t.get("term", "") for t in entry.get("tags", [])],
                                "content": [
                                    c.get("value", "")
                                    for c in entry.get("content", [])
                                ],
                            },
                            indent=2,
                        ),
                    )
                ]
        raise ValueError(f"Entry not found: {entry_id}")

    async def _feed_to_json(self, url: str) -> list[TextContent]:
        feed = self._parse(url)
        data = {
            "feed": {
                "title": feed.feed.get("title", ""),
                "link": feed.feed.get("link", ""),
                "description": feed.feed.get("description", ""),
                "language": feed.feed.get("language", ""),
                "author": feed.feed.get("author", ""),
            },
            "entries": [
                {
                    "title": e.get("title", ""),
                    "link": e.get("link", ""),
                    "published": e.get("published", ""),
                    "id": e.get("id", ""),
                    "summary": e.get("summary", ""),
                    "author": e.get("author", ""),
                    "tags": [t.get("term", "") for t in e.get("tags", [])],
                }
                for e in feed.entries
            ],
        }
        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = RssServer()
    async with stdio_server() as (read, write):
        await server.run(
            read, write, server.list_tools, server.call_tool,
            server.list_resources, server.read_resource,
        )

if __name__ == "__main__":
    anyio.run(main)
