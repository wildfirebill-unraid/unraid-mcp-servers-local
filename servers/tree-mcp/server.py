import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class TreeServer(Server):
    def __init__(self):
        super().__init__("tree")
        self._tree_path = os.environ.get("TREE_PATH", "")

    def _resolve_path(self, path: str) -> Path:
        p = Path(path).resolve()
        if self._tree_path:
            base = Path(self._tree_path).resolve()
            if not str(p).startswith(str(base)):
                raise ValueError(f"Path outside sandbox: {path}")
        return p

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="tree", description="Show directory tree as ASCII",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Directory path"},
                     "max_depth": {"type": "integer", "description": "Max depth (default unlimited)"},
                     "show_hidden": {"type": "boolean", "description": "Show hidden files (default false)"}},
                     "required": ["path"]}),
            Tool(name="tree_size", description="Recursive directory size",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Directory path"}},
                     "required": ["path"]}),
            Tool(name="tree_filter", description="Filtered directory tree by glob pattern",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Directory path"},
                     "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py')"},
                     "max_depth": {"type": "integer", "description": "Max depth"}},
                     "required": ["path", "pattern"]}),
            Tool(name="tree_json", description="Directory tree as JSON",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Directory path"},
                     "max_depth": {"type": "integer", "description": "Max depth"},
                     "show_hidden": {"type": "boolean", "description": "Show hidden files"}},
                     "required": ["path"]}),
            Tool(name="tree_xml", description="Directory tree as XML",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Directory path"},
                     "max_depth": {"type": "integer", "description": "Max depth"},
                     "show_hidden": {"type": "boolean", "description": "Show hidden files"}},
                     "required": ["path"]}),
            Tool(name="tree_compare", description="Compare two directory trees",
                 inputSchema={"type": "object", "properties": {
                     "path1": {"type": "string", "description": "First directory"},
                     "path2": {"type": "string", "description": "Second directory"}},
                     "required": ["path1", "path2"]}),
            Tool(name="dir_stat", description="File/dir count and total size",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Directory path"}},
                     "required": ["path"]}),
            Tool(name="find_deepest", description="Find deepest nested path",
                 inputSchema={"type": "object", "properties": {
                     "path": {"type": "string", "description": "Directory path"}},
                     "required": ["path"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "tree":
                result = self._tree(args)
            elif name == "tree_size":
                result = self._tree_size(args)
            elif name == "tree_filter":
                result = self._tree_filter(args)
            elif name == "tree_json":
                result = self._tree_json(args)
            elif name == "tree_xml":
                result = self._tree_xml(args)
            elif name == "tree_compare":
                result = self._tree_compare(args)
            elif name == "dir_stat":
                result = self._dir_stat(args)
            elif name == "find_deepest":
                result = self._find_deepest(args)
            else:
                raise ValueError(f"Unknown tool: {name}")
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    def _should_skip(self, name: str, show_hidden: bool) -> bool:
        return not show_hidden and name.startswith(".")

    def _build_ascii_tree(self, path: Path, prefix: str = "", depth: int = 0, max_depth: int = -1, show_hidden: bool = False) -> list[str]:
        if max_depth != -1 and depth > max_depth:
            return [f"{prefix}..."]
        lines = []
        entries = sorted([e for e in path.iterdir() if not self._should_skip(e.name, show_hidden)],
                         key=lambda x: (not x.is_dir(), x.name.lower()))
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                ext = "    " if is_last else "│   "
                lines.extend(self._build_ascii_tree(entry, prefix + ext, depth + 1, max_depth, show_hidden))
        return lines

    def _tree(self, args: dict) -> dict:
        p = self._resolve_path(args["path"])
        if not p.is_dir():
            raise ValueError(f"Not a directory: {p}")
        max_depth = args.get("max_depth", -1)
        show_hidden = args.get("show_hidden", False)
        lines = self._build_ascii_tree(p, max_depth=max_depth, show_hidden=show_hidden)
        return {"path": str(p), "tree": f"{p.name}/\n" + "\n".join(lines)}

    def _tree_size(self, args: dict) -> dict:
        p = self._resolve_path(args["path"])
        total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        return {"path": str(p), "size": total}

    def _tree_filter(self, args: dict) -> dict:
        p = self._resolve_path(args["path"])
        pattern = args["pattern"]
        max_depth = args.get("max_depth", -1)
        matches = []
        for f in sorted(p.rglob(pattern)):
            rel = f.relative_to(p)
            depth = len(rel.parents)
            if max_depth != -1 and depth > max_depth:
                continue
            matches.append(str(rel))
        return {"pattern": pattern, "matches": len(matches), "files": matches}

    def _build_json_tree(self, path: Path, depth: int = 0, max_depth: int = -1, show_hidden: bool = False) -> dict:
        result = {"name": path.name, "type": "directory" if path.is_dir() else "file"}
        if path.is_dir():
            if max_depth != -1 and depth > max_depth:
                return result
            children = []
            for e in sorted(path.iterdir(), key=lambda x: x.name.lower()):
                if self._should_skip(e.name, show_hidden):
                    continue
                children.append(self._build_json_tree(e, depth + 1, max_depth, show_hidden))
            result["children"] = children
        else:
            result["size"] = path.stat().st_size
        return result

    def _tree_json(self, args: dict) -> dict:
        p = self._resolve_path(args["path"])
        max_depth = args.get("max_depth", -1)
        show_hidden = args.get("show_hidden", False)
        return self._build_json_tree(p, max_depth=max_depth, show_hidden=show_hidden)

    def _build_xml_tree(self, parent: ET.Element, path: Path, depth: int = 0, max_depth: int = -1, show_hidden: bool = False):
        if path.is_dir():
            el = ET.SubElement(parent, "directory", name=path.name)
            if max_depth != -1 and depth > max_depth:
                return
            for e in sorted(path.iterdir(), key=lambda x: x.name.lower()):
                if self._should_skip(e.name, show_hidden):
                    continue
                self._build_xml_tree(el, e, depth + 1, max_depth, show_hidden)
        else:
            ET.SubElement(parent, "file", name=path.name, size=str(path.stat().st_size))

    def _tree_xml(self, args: dict) -> dict:
        p = self._resolve_path(args["path"])
        max_depth = args.get("max_depth", -1)
        show_hidden = args.get("show_hidden", False)
        root = ET.Element("tree")
        self._build_xml_tree(root, p, max_depth=max_depth, show_hidden=show_hidden)
        return {"xml": ET.tostring(root, encoding="unicode")}

    def _tree_compare(self, args: dict) -> dict:
        p1 = self._resolve_path(args["path1"])
        p2 = self._resolve_path(args["path2"])
        rel1 = {f.relative_to(p1) for f in p1.rglob("*") if f.is_file()}
        rel2 = {f.relative_to(p2) for f in p2.rglob("*") if f.is_file()}
        only_in_1 = sorted(str(x) for x in rel1 - rel2)
        only_in_2 = sorted(str(x) for x in rel2 - rel1)
        common = sorted(str(x) for x in rel1 & rel2)
        size_diffs = []
        for c in rel1 & rel2:
            s1 = (p1 / c).stat().st_size
            s2 = (p2 / c).stat().st_size
            if s1 != s2:
                size_diffs.append({"file": str(c), f"{p1.name}_size": s1, f"{p2.name}_size": s2})
        return {"only_in_first": only_in_1, "only_in_second": only_in_2, "common": len(common), "size_differences": size_diffs}

    def _dir_stat(self, args: dict) -> dict:
        p = self._resolve_path(args["path"])
        file_count = sum(1 for f in p.rglob("*") if f.is_file())
        dir_count = sum(1 for f in p.rglob("*") if f.is_dir())
        total_size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        return {"path": str(p), "files": file_count, "directories": dir_count, "total_size": total_size}

    def _find_deepest(self, args: dict) -> dict:
        p = self._resolve_path(args["path"])
        deepest = max((f for f in p.rglob("*") if f.is_file()), key=lambda x: len(x.parents), default=None)
        if deepest is None:
            return {"path": str(p), "deepest": None}
        depth = len(deepest.relative_to(p).parents)
        return {"path": str(p), "deepest": str(deepest.relative_to(p)), "depth": depth}

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = TreeServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
