import json
from typing import Any

from jsonpatch import JsonPatch, apply_patch as jsonpatch_apply
from jsonpatch import JsonPatchException
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


def _load_json(s: str) -> Any:
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def _deep_diff(a: Any, b: Any, path: str = "$") -> list[dict]:
    changes = []
    if a == b:
        return changes
    if type(a) != type(b):
        changes.append({"path": path, "from": repr(type(a).__name__), "to": repr(type(b).__name__), "old": a, "new": b})
        return changes
    if isinstance(a, dict):
        all_keys = set(a) | set(b)
        for k in sorted(all_keys):
            kpath = f"{path}.{k}" if path != "$" else f"$.{k}"
            if k not in a:
                changes.append({"path": kpath, "change": "added", "new": b[k]})
            elif k not in b:
                changes.append({"path": kpath, "change": "removed", "old": a[k]})
            else:
                changes.extend(_deep_diff(a[k], b[k], kpath))
    elif isinstance(a, list):
        max_len = max(len(a), len(b))
        for i in range(max_len):
            ipath = f"{path}[{i}]"
            if i >= len(a):
                changes.append({"path": ipath, "change": "added", "new": b[i]})
            elif i >= len(b):
                changes.append({"path": ipath, "change": "removed", "old": a[i]})
            else:
                changes.extend(_deep_diff(a[i], b[i], ipath))
    else:
        changes.append({"path": path, "change": "modified", "old": a, "new": b})
    return changes


class JsonMergePatchServer(Server):
    def __init__(self):
        super().__init__("json-merge-patch-server")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="merge_patch",
                description="Apply RFC 7386 JSON Merge Patch (shallow merge of target with patch)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target_json": {
                            "type": "string",
                            "description": "Target JSON document",
                        },
                        "patch_json": {
                            "type": "string",
                            "description": "JSON Merge Patch to apply",
                        },
                    },
                    "required": ["target_json", "patch_json"],
                },
            ),
            Tool(
                name="apply_patch",
                description="Apply RFC 6902 JSON Patch (array of operations) to a document",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "doc_json": {
                            "type": "string",
                            "description": "Source JSON document",
                        },
                        "patch_json": {
                            "type": "string",
                            "description": "JSON Patch (array of operation objects)",
                        },
                    },
                    "required": ["doc_json", "patch_json"],
                },
            ),
            Tool(
                name="generate_patch",
                description="Generate an RFC 6902 JSON Patch to transform source into target",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_json": {
                            "type": "string",
                            "description": "Source JSON document",
                        },
                        "target_json": {
                            "type": "string",
                            "description": "Target JSON document",
                        },
                    },
                    "required": ["source_json", "target_json"],
                },
            ),
            Tool(
                name="compare_json",
                description="Deep comparison of two JSON values with detailed differences",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "json1": {
                            "type": "string",
                            "description": "First JSON value",
                        },
                        "json2": {
                            "type": "string",
                            "description": "Second JSON value",
                        },
                    },
                    "required": ["json1", "json2"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "merge_patch":
            return await self._merge_patch(args["target_json"], args["patch_json"])
        if name == "apply_patch":
            return await self._apply_patch(args["doc_json"], args["patch_json"])
        if name == "generate_patch":
            return await self._generate_patch(args["source_json"], args["target_json"])
        if name == "compare_json":
            return await self._compare_json(args["json1"], args["json2"])
        raise ValueError(f"Unknown tool: {name}")

    async def _merge_patch(self, target_json: str, patch_json: str) -> list[TextContent]:
        target = _load_json(target_json)
        patch = _load_json(patch_json)
        if not isinstance(patch, dict):
            result = patch
        else:
            result = self._merge_recursive(target if isinstance(target, dict) else {}, patch)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    def _merge_recursive(self, target: dict, patch: dict) -> dict:
        result = target.copy() if isinstance(target, dict) else {}
        for k, v in patch.items():
            if v is None:
                result.pop(k, None)
            elif k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._merge_recursive(result[k], v)
            else:
                result[k] = v
        return result

    async def _apply_patch(self, doc_json: str, patch_json: str) -> list[TextContent]:
        doc = _load_json(doc_json)
        patch = _load_json(patch_json)
        try:
            result = jsonpatch_apply(doc, JsonPatch(patch))
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except JsonPatchException as e:
            raise ValueError(f"Patch application failed: {e}")

    async def _generate_patch(self, source_json: str, target_json: str) -> list[TextContent]:
        source = _load_json(source_json)
        target = _load_json(target_json)
        patch = JsonPatch.from_diff(source, target)
        return [TextContent(type="text", text=json.dumps(patch.patch, indent=2))]

    async def _compare_json(self, json1: str, json2: str) -> list[TextContent]:
        a = _load_json(json1)
        b = _load_json(json2)
        if a == b:
            return [TextContent(type="text", text=json.dumps({"equal": True, "changes": []}, indent=2))]
        changes = _deep_diff(a, b)
        return [
            TextContent(
                type="text",
                text=json.dumps({"equal": False, "changes": changes}, indent=2),
            )
        ]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = JsonMergePatchServer()
    async with stdio_server() as (read, write):
        await server.run(
            read, write, server.list_tools, server.call_tool,
            server.list_resources, server.read_resource,
        )

if __name__ == "__main__":
    anyio.run(main)
