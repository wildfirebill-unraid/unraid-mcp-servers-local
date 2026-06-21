import sys
import json
import os
import subprocess
import base64
import math
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

BASE62_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

BASE_INFO = {
    2: {"name": "Binary", "prefix": "0b", "digits": "01"},
    8: {"name": "Octal", "prefix": "0o", "digits": "0-7"},
    10: {"name": "Decimal", "prefix": "", "digits": "0-9"},
    16: {"name": "Hexadecimal", "prefix": "0x", "digits": "0-9, A-F"},
    32: {"name": "Base32", "prefix": "b32:", "digits": "A-Z, 2-7", "standard": "RFC 4648"},
    36: {"name": "Base36", "prefix": "", "digits": "0-9, A-Z"},
    62: {"name": "Base62", "prefix": "", "digits": "0-9, a-z, A-Z"},
    64: {"name": "Base64", "prefix": "b64:", "digits": "A-Z, a-z, 0-9, +, /, =", "standard": "RFC 4648"},
}

PREFIX_MAP = [
    ("0b", 2), ("0o", 8), ("0x", 16), ("0X", 16),
    ("b32:", 32), ("b64:", 64),
]


def _from_base62(s: str, base: int) -> int:
    if base > 62:
        raise ValueError(f"Base {base} not supported for decode_value (max 62)")
    chars = BASE62_CHARS[:base]
    result = 0
    for c in s:
        val = chars.find(c)
        if val < 0:
            raise ValueError(f"Invalid character '{c}' for base {base}")
        result = result * base + val
    return result


def _to_base62(n: int, base: int) -> str:
    if base > 62:
        raise ValueError(f"Base {base} not supported for encode_value (max 62)")
    if n == 0:
        return BASE62_CHARS[0]
    chars = BASE62_CHARS[:base]
    result = []
    while n > 0:
        result.append(chars[n % base])
        n //= base
    return "".join(reversed(result))


class BasexServer(Server):
    def __init__(self):
        super().__init__("basex")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="encode_value", description="Convert a value from one base to another (bases 2-62)", inputSchema={"type": "object", "properties": {"value": {"type": "string", "description": "Value to convert"}, "from_base": {"type": "integer", "description": "Source base (2-62)"}, "to_base": {"type": "integer", "description": "Target base (2-62)"}}, "required": ["value", "from_base", "to_base"]}),
            Tool(name="decode_value", description="Decode a value from a given base to decimal", inputSchema={"type": "object", "properties": {"encoded_value": {"type": "string", "description": "Value to decode"}, "from_base": {"type": "integer", "description": "Source base (2-62)"}}, "required": ["encoded_value", "from_base"]}),
            Tool(name="list_bases", description="List supported base formats and their properties", inputSchema={"type": "object", "properties": {}}),
            Tool(name="encode_bytes", description="Encode raw bytes (base64 input) to a base string", inputSchema={"type": "object", "properties": {"data_b64": {"type": "string", "description": "Base64-encoded input data"}, "base": {"type": "integer", "description": "Target base (2-64)"}}, "required": ["data_b64", "base"]}),
            Tool(name="decode_bytes", description="Decode a base string to bytes (returned as hex)", inputSchema={"type": "object", "properties": {"encoded": {"type": "string", "description": "Encoded string to decode"}, "base": {"type": "integer", "description": "Source base (2-64)"}}, "required": ["encoded", "base"]}),
            Tool(name="detect_base", description="Auto-detect base from value prefix (0b, 0o, 0x, b32:, b64:)", inputSchema={"type": "object", "properties": {"value": {"type": "string", "description": "Value whose base to detect"}}, "required": ["value"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "encode_value":
                value = args.get("value", "")
                from_base = int(args.get("from_base", 10))
                to_base = int(args.get("to_base", 10))
                if from_base < 2 or from_base > 62:
                    raise ValueError("from_base must be between 2 and 62")
                if to_base < 2 or to_base > 62:
                    raise ValueError("to_base must be between 2 and 62")
                decimal = _from_base62(value.strip(), from_base)
                result_str = _to_base62(decimal, to_base)
                return [TextContent(type="text", text=json.dumps({"input": value, "from_base": from_base, "to_base": to_base, "result": result_str, "decimal": decimal}))]

            if name == "decode_value":
                encoded = args.get("encoded_value", "")
                from_base = int(args.get("from_base", 10))
                if from_base < 2 or from_base > 62:
                    raise ValueError("from_base must be between 2 and 62")
                decimal = _from_base62(encoded.strip(), from_base)
                return [TextContent(type="text", text=json.dumps({"input": encoded, "from_base": from_base, "decimal": decimal, "hex": hex(decimal), "octal": oct(decimal), "binary": bin(decimal)}))]

            if name == "list_bases":
                bases = []
                for b, info in sorted(BASE_INFO.items()):
                    bases.append({"base": b, "name": info["name"], "prefix": info["prefix"], "digits": info["digits"]})
                return [TextContent(type="text", text=json.dumps({"bases": bases}))]

            if name == "encode_bytes":
                data_b64 = args.get("data_b64", "")
                base_target = int(args.get("base", 10))
                if base_target < 2 or base_target > 64:
                    raise ValueError("base must be between 2 and 64")
                try:
                    raw_bytes = base64.b64decode(data_b64)
                except Exception:
                    raise ValueError("Invalid base64 input")
                if base_target == 64:
                    result_str = base64.b64encode(raw_bytes).decode("ascii")
                else:
                    n = int.from_bytes(raw_bytes, "big")
                    result_str = _to_base62(n, base_target) if n > 0 else BASE62_CHARS[0]
                return [TextContent(type="text", text=json.dumps({"input_b64": data_b64, "base": base_target, "result": result_str, "byte_length": len(raw_bytes)}))]

            if name == "decode_bytes":
                encoded = args.get("encoded", "")
                base_src = int(args.get("base", 10))
                if base_src < 2 or base_src > 64:
                    raise ValueError("base must be between 2 and 64")
                if base_src == 64:
                    try:
                        raw_bytes = base64.b64decode(encoded)
                    except Exception:
                        try:
                            raw_bytes = base64.b64decode(encoded + "==")
                        except Exception:
                            raise ValueError("Invalid base64 input")
                else:
                    n = _from_base62(encoded.strip(), base_src)
                    byte_len = (n.bit_length() + 7) // 8
                    raw_bytes = n.to_bytes(max(byte_len, 1), "big")
                return [TextContent(type="text", text=json.dumps({"input": encoded, "base": base_src, "hex": raw_bytes.hex(), "byte_length": len(raw_bytes)}))]

            if name == "detect_base":
                value = args.get("value", "").strip()
                detected = None
                for prefix, base in PREFIX_MAP:
                    if value.startswith(prefix):
                        detected = {"base": base, "prefix": prefix, "clean_value": value[len(prefix):]}
                        break
                if detected:
                    info = BASE_INFO.get(detected["base"], {})
                    detected["name"] = info.get("name", f"Base {detected['base']}")
                    return [TextContent(type="text", text=json.dumps({"value": value, "detected": detected}))]
                else:
                    return [TextContent(type="text", text=json.dumps({"value": value, "detected": None, "note": "No standard prefix found; try decode_value with explicit base"}))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = BasexServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
