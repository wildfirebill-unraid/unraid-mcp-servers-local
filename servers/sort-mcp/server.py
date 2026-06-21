import os
import json
import random
import re
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("sort-mcp")

def natural_sort_key(s: str):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="sort_lines",
            description="Sort lines of text with various options",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to sort"},
                    "reverse": {"type": "boolean", "description": "Sort in reverse order"},
                    "ignore_case": {"type": "boolean", "description": "Ignore case when sorting"},
                    "numeric": {"type": "boolean", "description": "Natural sort (numbers within text)"},
                    "unique": {"type": "boolean", "description": "Remove duplicates after sorting"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="shuffle_lines",
            description="Randomly shuffle lines of text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to shuffle"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="sample_lines",
            description="Randomly sample N lines from text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to sample from"},
                    "count": {"type": "integer", "description": "Number of lines to sample"}
                },
                "required": ["text", "count"]
            }
        ),
        Tool(
            name="filter_lines",
            description="Keep lines matching a pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to filter"},
                    "pattern": {"type": "string", "description": "Regex pattern to match"},
                    "invert": {"type": "boolean", "description": "Exclude matching lines instead of keeping them"},
                    "ignore_case": {"type": "boolean", "description": "Ignore case when matching"}
                },
                "required": ["text", "pattern"]
            }
        ),
        Tool(
            name="deduplicate_lines",
            description="Remove duplicate lines preserving order",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to deduplicate"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="split_text",
            description="Split text into chunks by lines, words, or bytes",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to split"},
                    "chunk_size": {"type": "integer", "description": "Size of each chunk"},
                    "chunk_unit": {
                        "type": "string",
                        "description": "Unit for chunking: lines, words, bytes",
                        "enum": ["lines", "words", "bytes"]
                    }
                },
                "required": ["text", "chunk_size", "chunk_unit"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "sort_lines":
        text = arguments["text"]
        lines = text.splitlines(keepends=True)
        reverse = arguments.get("reverse", False)
        ignore_case = arguments.get("ignore_case", False)
        numeric = arguments.get("numeric", False)
        unique = arguments.get("unique", False)
        if numeric:
            lines.sort(key=natural_sort_key, reverse=reverse)
        elif ignore_case:
            lines.sort(key=lambda s: s.lower(), reverse=reverse)
        else:
            lines.sort(reverse=reverse)
        if unique:
            seen = set()
            result_lines = []
            for line in lines:
                key = line.lower() if ignore_case else line
                if key not in seen:
                    seen.add(key)
                    result_lines.append(line)
            lines = result_lines
        result = "".join(lines)
    elif name == "shuffle_lines":
        lines = arguments["text"].splitlines(keepends=True)
        random.shuffle(lines)
        result = "".join(lines)
    elif name == "sample_lines":
        lines = arguments["text"].splitlines(keepends=True)
        count = min(arguments["count"], len(lines))
        sampled = random.sample(lines, count)
        result = "".join(sampled)
    elif name == "filter_lines":
        text = arguments["text"]
        pattern = arguments["pattern"]
        invert = arguments.get("invert", False)
        ignore_case = arguments.get("ignore_case", False)
        flags = re.IGNORECASE if ignore_case else 0
        lines = text.splitlines(keepends=True)
        if invert:
            filtered = [l for l in lines if not re.search(pattern, l, flags)]
        else:
            filtered = [l for l in lines if re.search(pattern, l, flags)]
        result = "".join(filtered)
    elif name == "deduplicate_lines":
        text = arguments["text"]
        lines = text.splitlines(keepends=True)
        seen = set()
        deduped = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                deduped.append(line)
        result = "".join(deduped)
    elif name == "split_text":
        text = arguments["text"]
        chunk_size = arguments["chunk_size"]
        chunk_unit = arguments["chunk_unit"]
        chunks = []
        if chunk_unit == "lines":
            lines = text.splitlines(keepends=True)
            for i in range(0, len(lines), chunk_size):
                chunks.append("".join(lines[i:i + chunk_size]))
        elif chunk_unit == "words":
            words = text.split()
            for i in range(0, len(words), chunk_size):
                chunks.append(" ".join(words[i:i + chunk_size]))
        elif chunk_unit == "bytes":
            encoded = text.encode("utf-8")
            for i in range(0, len(encoded), chunk_size):
                chunks.append(encoded[i:i + chunk_size].decode("utf-8", errors="replace"))
        result = json.dumps({"chunks": chunks, "count": len(chunks)})
    else:
        raise ValueError(f"Unknown tool: {name}")
    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="sort-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
