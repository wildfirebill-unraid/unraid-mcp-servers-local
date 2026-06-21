import os
import json
import re
import base64
import hashlib
import html as html_mod
import urllib.parse
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("text-utility-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="regex_find",
            description="Find all regex matches in text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to search in"},
                    "pattern": {"type": "string", "description": "Regex pattern"}
                },
                "required": ["text", "pattern"]
            }
        ),
        Tool(
            name="regex_replace",
            description="Replace regex matches in text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Input text"},
                    "pattern": {"type": "string", "description": "Regex pattern"},
                    "replacement": {"type": "string", "description": "Replacement string"}
                },
                "required": ["text", "pattern", "replacement"]
            }
        ),
        Tool(
            name="validate_json",
            description="Check if a string is valid JSON and optionally validate structure",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "String to validate as JSON"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="format_json",
            description="Pretty-print JSON string with indentation",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "JSON string to format"},
                    "indent": {"type": "integer", "description": "Indentation spaces (default 2)"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="minify_json",
            description="Minify a JSON string by removing whitespace",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "JSON string to minify"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="encode_base64",
            description="Encode text to base64",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to encode"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="decode_base64",
            description="Decode base64 to text",
            inputSchema={
                "type": "object",
                "properties": {
                    "encoded": {"type": "string", "description": "Base64 encoded string"}
                },
                "required": ["encoded"]
            }
        ),
        Tool(
            name="hash_text",
            description="Compute hash of text (md5, sha1, sha256, sha512)",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to hash"},
                    "algorithm": {"type": "string", "description": "Hash algorithm: md5, sha1, sha256, sha512 (default sha256)"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="url_encode",
            description="URL-encode a string",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to URL-encode"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="url_decode",
            description="URL-decode a string",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "URL-encoded text to decode"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="html_encode",
            description="HTML-encode special characters",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to HTML-encode"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="html_decode",
            description="HTML-decode entities",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "HTML string to decode"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="count_words",
            description="Count words, characters, lines, and sentences in text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to analyze"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="escape_shell",
            description="Escape text for use in shell commands",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to escape"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="csv_to_json",
            description="Convert CSV text to JSON array",
            inputSchema={
                "type": "object",
                "properties": {
                    "csv": {"type": "string", "description": "CSV content (first row = headers)"}
                },
                "required": ["csv"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = ""

    if name == "regex_find":
        matches = re.findall(arguments["pattern"], arguments["text"])
        result = str(matches)

    elif name == "regex_replace":
        result = re.sub(arguments["pattern"], arguments["replacement"], arguments["text"])

    elif name == "validate_json":
        try:
            parsed = json.loads(arguments["text"])
            result = str({"valid": True, "type": type(parsed).__name__})
        except json.JSONDecodeError as e:
            result = str({"valid": False, "error": str(e)})

    elif name == "format_json":
        indent = arguments.get("indent", 2)
        parsed = json.loads(arguments["text"])
        result = json.dumps(parsed, indent=indent, ensure_ascii=False, sort_keys=False)

    elif name == "minify_json":
        parsed = json.loads(arguments["text"])
        result = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)

    elif name == "encode_base64":
        result = base64.b64encode(arguments["text"].encode()).decode()

    elif name == "decode_base64":
        result = base64.b64decode(arguments["encoded"]).decode("utf-8", errors="replace")

    elif name == "hash_text":
        algo = arguments.get("algorithm", "sha256")
        text = arguments["text"].encode()
        if algo == "md5":
            result = hashlib.md5(text).hexdigest()
        elif algo == "sha1":
            result = hashlib.sha1(text).hexdigest()
        elif algo == "sha256":
            result = hashlib.sha256(text).hexdigest()
        elif algo == "sha512":
            result = hashlib.sha512(text).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algo}")

    elif name == "url_encode":
        result = urllib.parse.quote(arguments["text"], safe="")

    elif name == "url_decode":
        result = urllib.parse.unquote(arguments["text"])

    elif name == "html_encode":
        result = html_mod.escape(arguments["text"])

    elif name == "html_decode":
        result = html_mod.unescape(arguments["text"])

    elif name == "count_words":
        text = arguments["text"]
        words = len(text.split())
        chars = len(text)
        lines = text.count("\n") + 1
        sentences = len(re.findall(r'[.!?]+', text))
        result = str({"words": words, "characters": chars, "lines": lines, "sentences": sentences})

    elif name == "escape_shell":
        text = arguments["text"]
        result = "'" + text.replace("'", "'\\''") + "'"

    elif name == "csv_to_json":
        lines = [l.strip() for l in arguments["csv"].split("\n") if l.strip()]
        if not lines:
            result = "[]"
        else:
            headers = [h.strip() for h in lines[0].split(",")]
            rows = []
            for line in lines[1:]:
                values = [v.strip() for v in line.split(",")]
                row = {}
                for i, h in enumerate(headers):
                    row[h] = values[i] if i < len(values) else ""
                rows.append(row)
            result = json.dumps(rows, indent=2)

    else:
        raise ValueError(f"Unknown tool: {name}")

    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="text-utility-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
