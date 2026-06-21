import hashlib
import json
import os
import glob as glob_mod
from pathlib import Path

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class HashServer(Server):
    def __init__(self):
        super().__init__("hash")
        self._init_env()

    def _init_env(self):
        self._hash_path = os.environ.get("HASH_PATH", "")

    def _resolve_path(self, given: str) -> str:
        p = Path(given)
        if p.is_absolute():
            if self._hash_path:
                base = Path(self._hash_path).resolve()
                resolved = p.resolve()
                if base not in resolved.parents and resolved != base:
                    raise PermissionError(f"Path {given} is outside allowed base {self._hash_path}")
            return str(p.resolve())
        if self._hash_path:
            return str((Path(self._hash_path) / p).resolve())
        return str(p.resolve())

    def _hash_text_impl(self, text: str, algorithm: str) -> str:
        try:
            h = hashlib.new(algorithm, text.encode("utf-8"))
            return h.hexdigest()
        except ValueError:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

    def _hash_file_impl(self, path: str, algorithm: str) -> str:
        resolved = self._resolve_path(path)
        try:
            h = hashlib.new(algorithm)
        except ValueError:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        with open(resolved, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="hash_text", description="Hash text with specified algorithm (md5/sha1/sha256/sha512/blake2b)", inputSchema={"type":"object","properties":{"text":{"type":"string","description":"Text to hash"},"algorithm":{"type":"string","description":"Hash algorithm","default":"sha256"}},"required":["text"]}),
            Tool(name="hash_file", description="Hash a file with specified algorithm (paths sandboxed to HASH_PATH)", inputSchema={"type":"object","properties":{"path":{"type":"string","description":"Path to file"},"algorithm":{"type":"string","description":"Hash algorithm","default":"sha256"}},"required":["path"]}),
            Tool(name="hash_stream", description="Memory-efficient large file hash with configurable chunk size", inputSchema={"type":"object","properties":{"path":{"type":"string","description":"Path to file"},"algorithm":{"type":"string","description":"Hash algorithm","default":"sha256"},"chunk_size":{"type":"integer","description":"Chunk size in bytes","default":65536}},"required":["path"]}),
            Tool(name="hash_compare", description="Constant-time comparison of two hash strings", inputSchema={"type":"object","properties":{"hash1":{"type":"string","description":"First hash"},"hash2":{"type":"string","description":"Second hash"}},"required":["hash1","hash2"]}),
            Tool(name="hash_verify", description="Verify a file matches an expected hash", inputSchema={"type":"object","properties":{"path":{"type":"string","description":"Path to file"},"expected_hash":{"type":"string","description":"Expected hash value"},"algorithm":{"type":"string","description":"Hash algorithm","default":"sha256"}},"required":["path","expected_hash"]}),
            Tool(name="list_algorithms", description="List all available hash algorithms", inputSchema={"type":"object","properties":{}}),
            Tool(name="hash_directory", description="Hash all files matching a glob pattern in a directory", inputSchema={"type":"object","properties":{"path":{"type":"string","description":"Directory path"},"pattern":{"type":"string","description":"Glob pattern (e.g. *.txt, **/*.py)","default":"*"}},"required":["path"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "hash_text":
            text = args.get("text", "")
            algorithm = args.get("algorithm", "sha256")
            result = self._hash_text_impl(text, algorithm)
            return [TextContent(type="text", text=json.dumps({"algorithm": algorithm, "hash": result}))]

        if name == "hash_file":
            path = args.get("path", "")
            algorithm = args.get("algorithm", "sha256")
            result = self._hash_file_impl(path, algorithm)
            return [TextContent(type="text", text=json.dumps({"path": path, "algorithm": algorithm, "hash": result}))]

        if name == "hash_stream":
            path = args.get("path", "")
            algorithm = args.get("algorithm", "sha256")
            chunk_size = args.get("chunk_size", 65536)
            resolved = self._resolve_path(path)
            try:
                h = hashlib.new(algorithm)
            except ValueError:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
            with open(resolved, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    h.update(chunk)
            return [TextContent(type="text", text=json.dumps({"path": path, "algorithm": algorithm, "chunk_size": chunk_size, "hash": h.hexdigest()}))]

        if name == "hash_compare":
            h1 = args.get("hash1", "")
            h2 = args.get("hash2", "")
            match = hmac_compare(h1, h2)
            return [TextContent(type="text", text=json.dumps({"hash1": h1, "hash2": h2, "match": match}))]

        if name == "hash_verify":
            path = args.get("path", "")
            expected = args.get("expected_hash", "")
            algorithm = args.get("algorithm", "sha256")
            actual = self._hash_file_impl(path, algorithm)
            match = hmac_compare(actual, expected)
            return [TextContent(type="text", text=json.dumps({"path": path, "algorithm": algorithm, "expected": expected, "actual": actual, "match": match}))]

        if name == "list_algorithms":
            algs = sorted(hashlib.algorithms_available)
            return [TextContent(type="text", text=json.dumps({"algorithms": algs}))]

        if name == "hash_directory":
            dir_path = args.get("path", "")
            pattern = args.get("pattern", "*")
            resolved_dir = self._resolve_path(dir_path)
            results = {}
            for fp in sorted(glob_mod.glob(pattern, root_dir=resolved_dir)):
                full = os.path.join(resolved_dir, fp)
                if os.path.isfile(full):
                    h = hashlib.sha256()
                    with open(full, "rb") as f:
                        for chunk in iter(lambda: f.read(65536), b""):
                            h.update(chunk)
                    results[fp] = h.hexdigest()
            return [TextContent(type="text", text=json.dumps({"path": dir_path, "pattern": pattern, "files": results}))]

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


def hmac_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    result = 0
    for ca, cb in zip(a, b):
        result |= ord(ca) ^ ord(cb)
    return result == 0


async def main():
    server = HashServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
