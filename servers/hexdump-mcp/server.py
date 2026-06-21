import os
import json
import math
import binascii
import struct
from pathlib import Path
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class HexdumpServer(Server):
    def __init__(self):
        super().__init__("hexdump")
        self._hexdump_path = os.environ.get("HEXDUMP_PATH", "")

    def _resolve_path(self, path: str) -> Path:
        p = Path(path).resolve()
        if self._hexdump_path:
            base = Path(self._hexdump_path).resolve()
            if not str(p).startswith(str(base)):
                raise ValueError(f"Path outside sandbox: {path}")
        return p

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="hex_dump", description="Classic hex+ASCII dump of a file",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "File path"},
                     "width": {"type": "integer", "description": "Bytes per line (default 16)"},
                     "length": {"type": "integer", "description": "Max bytes to read"},
                     "offset": {"type": "integer", "description": "Byte offset to start"}},
                     "required": ["path"]}),
            Tool(name="hex_diff", description="Show hex diff offsets between two files",
                 inputSchema={"type": "object", "properties": {
                     "path1": {"type": "string", "description": "First file"},
                     "path2": {"type": "string", "description": "Second file"}},
                     "required": ["path1", "path2"]}),
            Tool(name="hex_search", description="Search for hex bytes in a file",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "File path"},
                     "hex_pattern": {"type": "string", "description": "Hex string to search for (e.g. 'A1B2')"}},
                     "required": ["path", "hex_pattern"]}),
            Tool(name="hex_stat", description="File size and entropy estimate",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "File path"}},
                     "required": ["path"]}),
            Tool(name="hex_compare", description="Compare two files byte by byte",
                 inputSchema={"type": "object", "properties": {
                     "path1": {"type": "string", "description": "First file"},
                     "path2": {"type": "string", "description": "Second file"}},
                     "required": ["path1", "path2"]}),
            Tool(name="bin_to_hex", description="Convert binary string to hex",
                 inputSchema={"type": "object", "properties": {
                     "data": {"type": "string", "description": "Binary data as string"}},
                     "required": ["data"]}),
            Tool(name="hex_to_bin", description="Convert hex string to binary",
                 inputSchema={"type": "object", "properties": {
                     "hex_str": {"type": "string", "description": "Hex string"}},
                     "required": ["hex_str"]}),
            Tool(name="hex_table", description="Show hex table for byte values",
                 inputSchema={"type": "object", "properties": {
                     "start": {"type": "integer", "description": "Start byte value (0-255, default 0)"},
                     "end": {"type": "integer", "description": "End byte value (0-255, default 255)"}},
                     "required": []}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "hex_dump":
                result = self._hex_dump(args)
            elif name == "hex_diff":
                result = self._hex_diff(args)
            elif name == "hex_search":
                result = self._hex_search(args)
            elif name == "hex_stat":
                result = self._hex_stat(args)
            elif name == "hex_compare":
                result = self._hex_compare(args)
            elif name == "bin_to_hex":
                result = self._bin_to_hex(args)
            elif name == "hex_to_bin":
                result = self._hex_to_bin(args)
            elif name == "hex_table":
                result = self._hex_table(args)
            else:
                raise ValueError(f"Unknown tool: {name}")
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    def _hex_dump(self, args: dict) -> dict:
        p = self._resolve_path(args["path"])
        width = args.get("width", 16)
        offset = args.get("offset", 0)
        length = args.get("length", 0)

        with open(p, "rb") as f:
            if offset:
                f.seek(offset)
            data = f.read(length) if length else f.read()

        lines = []
        for i in range(0, len(data), width):
            chunk = data[i:i + width]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            addr = offset + i
            lines.append(f"{addr:08x}  {hex_part:<{width * 3}}  |{ascii_part}|")
        return {"offset": offset, "length": len(data), "dump": "\n".join(lines)}

    def _hex_diff(self, args: dict) -> dict:
        p1 = self._resolve_path(args["path1"])
        p2 = self._resolve_path(args["path2"])
        d1 = open(p1, "rb").read()
        d2 = open(p2, "rb").read()
        diffs = []
        for i in range(max(len(d1), len(d2))):
            b1 = d1[i] if i < len(d1) else None
            b2 = d2[i] if i < len(d2) else None
            if b1 != b2:
                diffs.append({"offset": i, f"{p1.name}": f"{b1:02x}" if b1 is not None else "EOF",
                             f"{p2.name}": f"{b2:02x}" if b2 is not None else "EOF"})
        return {"diff_count": len(diffs), "diffs": diffs[:200]}

    def _hex_search(self, args: dict) -> dict:
        p = self._resolve_path(args["path"])
        pattern = binascii.unhexlify(args["hex_pattern"].replace(" ", ""))
        data = open(p, "rb").read()
        offsets = []
        start = 0
        while True:
            pos = data.find(pattern, start)
            if pos == -1:
                break
            offsets.append(pos)
            start = pos + 1
        return {"pattern": args["hex_pattern"], "matches": len(offsets), "offsets": offsets[:500]}

    def _hex_stat(self, args: dict) -> dict:
        p = self._resolve_path(args["path"])
        data = open(p, "rb").read()
        size = len(data)
        if size == 0:
            return {"path": str(p), "size": 0, "entropy": 0.0}
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        entropy = -sum((c / size) * math.log2(c / size) for c in freq if c > 0)
        return {"path": str(p), "size": size, "entropy": round(entropy, 4)}

    def _hex_compare(self, args: dict) -> dict:
        p1 = self._resolve_path(args["path1"])
        p2 = self._resolve_path(args["path2"])
        d1 = open(p1, "rb").read()
        d2 = open(p2, "rb").read()
        if d1 == d2:
            return {"equal": True, "size": len(d1)}
        first_diff = None
        for i in range(max(len(d1), len(d2))):
            b1 = d1[i] if i < len(d1) else None
            b2 = d2[i] if i < len(d2) else None
            if b1 != b2:
                first_diff = i
                break
        return {"equal": False, "size1": len(d1), "size2": len(d2), "first_diff_offset": first_diff}

    def _bin_to_hex(self, args: dict) -> dict:
        data = args["data"].encode("latin-1") if isinstance(args["data"], str) else args["data"]
        return {"hex": binascii.hexlify(data).decode("ascii")}

    def _hex_to_bin(self, args: dict) -> dict:
        clean = args["hex_str"].replace(" ", "").replace("\n", "")
        raw = binascii.unhexlify(clean)
        return {"binary": raw.decode("latin-1")}

    def _hex_table(self, args: dict) -> dict:
        start = max(0, min(args.get("start", 0), 255))
        end = max(0, min(args.get("end", 255), 255))
        if start > end:
            start, end = end, start
        rows = []
        for i in range(start, end + 1, 16):
            row = [f"{i:02x}"]
            for j in range(16):
                val = i + j
                if val > end:
                    break
                row.append(f"{val:02x}")
            rows.append(" ".join(row))
        return {"start": start, "end": end, "table": "\n".join(rows)}

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = HexdumpServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
