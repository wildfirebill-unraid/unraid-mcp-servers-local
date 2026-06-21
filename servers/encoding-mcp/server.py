import os
import json
from pathlib import Path
import unicodedata
import chardet
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("encoding-mcp")

BASE_PATH = Path(os.environ.get("ENCODING_PATH", "/data")).resolve()

def safe_path(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = BASE_PATH / p
    return p.resolve()

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="detect_encoding",
            description="Detect character encoding of a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="convert_encoding",
            description="Convert a file's character encoding",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "from_encoding": {"type": "string", "description": "Source encoding"},
                    "to_encoding": {"type": "string", "description": "Target encoding (default utf-8)"},
                    "output": {"type": "string", "description": "Output path (optional, in-place if omitted)"}
                },
                "required": ["path", "from_encoding"]
            }
        ),
        Tool(
            name="convert_text_encoding",
            description="Convert a text string's encoding",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to convert"},
                    "from_encoding": {"type": "string", "description": "Source encoding name"},
                    "to_encoding": {"type": "string", "description": "Target encoding name (default utf-8)"}
                },
                "required": ["text", "from_encoding"]
            }
        ),
        Tool(
            name="normalize_unicode",
            description="Normalize unicode text to a standard form",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to normalize"},
                    "form": {
                        "type": "string",
                        "description": "Unicode normalization form: NFC, NFD, NFKC, NFKD",
                        "enum": ["NFC", "NFD", "NFKC", "NFKD"]
                    }
                },
                "required": ["text", "form"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "detect_encoding":
        filepath = safe_path(arguments["path"])
        raw = filepath.read_bytes()
        detected = chardet.detect(raw)
        result = json.dumps({
            "encoding": detected.get("encoding"),
            "confidence": detected.get("confidence"),
            "language": detected.get("language")
        })
    elif name == "convert_encoding":
        filepath = safe_path(arguments["path"])
        from_enc = arguments["from_encoding"]
        to_enc = arguments.get("to_encoding", "utf-8")
        output = arguments.get("output")
        raw = filepath.read_bytes()
        decoded = raw.decode(from_enc, errors="replace")
        encoded = decoded.encode(to_enc, errors="replace")
        out_path = safe_path(output) if output else filepath
        out_path.write_bytes(encoded)
        result = json.dumps({"path": str(out_path), "from": from_enc, "to": to_enc})
    elif name == "convert_text_encoding":
        text = arguments["text"]
        from_enc = arguments["from_encoding"]
        to_enc = arguments.get("to_encoding", "utf-8")
        decoded = text.encode("utf-8").decode(from_enc, errors="replace")
        encoded = decoded.encode(to_enc, errors="replace")
        result = json.dumps({"result": encoded.decode(to_enc, errors="replace"),
                             "from": from_enc, "to": to_enc})
    elif name == "normalize_unicode":
        text = arguments["text"]
        form = arguments["form"]
        normalized = unicodedata.normalize(form, text)
        result = json.dumps({"result": normalized, "form": form,
                             "original_length": len(text), "normalized_length": len(normalized)})
    else:
        raise ValueError(f"Unknown tool: {name}")
    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="encoding-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
