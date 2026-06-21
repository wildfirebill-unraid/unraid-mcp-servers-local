import json

import semver
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class SemverServer(Server):
    def __init__(self):
        super().__init__("semver")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="parse_version",
                description="Parse a semver string into its components",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "version": {"type": "string", "description": "Semver version string (e.g. 1.2.3)"},
                    },
                    "required": ["version"],
                },
            ),
            Tool(
                name="compare_versions",
                description="Compare two semver versions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "v1": {"type": "string", "description": "First version"},
                        "v2": {"type": "string", "description": "Second version"},
                    },
                    "required": ["v1", "v2"],
                },
            ),
            Tool(
                name="bump_version",
                description="Bump a version by part (major/minor/patch/prerelease)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "version": {"type": "string", "description": "Current version"},
                        "part": {"type": "string", "enum": ["major", "minor", "patch", "prerelease"], "description": "Which part to bump"},
                        "pre_release": {"type": "string", "description": "Prerelease identifier (used when part=prerelease)"},
                    },
                    "required": ["version", "part"],
                },
            ),
            Tool(
                name="validate_version",
                description="Check if a version string is valid semver",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "version": {"type": "string", "description": "Version string to validate"},
                    },
                    "required": ["version"],
                },
            ),
            Tool(
                name="satisfies_range",
                description="Check if a version satisfies a range expression",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "version": {"type": "string", "description": "Version to check"},
                        "range_expr": {"type": "string", "description": "Range expression (e.g. ^1.0.0, >=2.0.0, ~1.2.0)"},
                    },
                    "required": ["version", "range_expr"],
                },
            ),
            Tool(
                name="sort_versions",
                description="Sort a list of version strings in ascending order",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "versions": {"type": "array", "items": {"type": "string"}, "description": "Array of version strings"},
                    },
                    "required": ["versions"],
                },
            ),
            Tool(
                name="latest_version",
                description="Find the latest version from a list",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "versions": {"type": "array", "items": {"type": "string"}, "description": "Array of version strings"},
                    },
                    "required": ["versions"],
                },
            ),
            Tool(
                name="version_diff",
                description="Show the difference type between two versions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "v1": {"type": "string", "description": "First version"},
                        "v2": {"type": "string", "description": "Second version"},
                    },
                    "required": ["v1", "v2"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "parse_version":
                v = semver.Version.parse(args["version"])
                return [TextContent(type="text", text=json.dumps({
                    "major": v.major, "minor": v.minor, "patch": v.patch,
                    "prerelease": v.prerelease, "build": v.build, "string": str(v),
                }))]
            if name == "compare_versions":
                result = semver.compare(args["v1"], args["v2"])
                labels = {-1: f"{args['v1']} < {args['v2']}", 0: f"{args['v1']} == {args['v2']}", 1: f"{args['v1']} > {args['v2']}"}
                return [TextContent(type="text", text=json.dumps({"comparison": result, "label": labels[result]}))]
            if name == "bump_version":
                version = args["version"]
                part = args["part"]
                pre = args.get("pre_release")
                if part == "major":
                    result = semver.bump_major(version)
                elif part == "minor":
                    result = semver.bump_minor(version)
                elif part == "patch":
                    result = semver.bump_patch(version)
                elif part == "prerelease":
                    v = semver.Version.parse(version)
                    if v.prerelease:
                        result = str(v.bump_prerelease())
                    else:
                        v = v.bump_patch()
                        v = v.replace(prerelease=pre or "alpha")
                        result = str(v)
                else:
                    raise ValueError(f"Unknown part: {part}")
                return [TextContent(type="text", text=json.dumps({"version": result}))]
            if name == "validate_version":
                valid = semver.Version.is_valid(args["version"])
                return [TextContent(type="text", text=json.dumps({"valid": valid}))]
            if name == "satisfies_range":
                result = semver.match(args["version"], args["range_expr"])
                return [TextContent(type="text", text=json.dumps({"satisfies": result}))]
            if name == "sort_versions":
                versions = args["versions"]
                parsed = [(semver.Version.parse(v), v) for v in versions]
                parsed.sort(key=lambda x: x[0])
                sorted_versions = [p[1] for p in parsed]
                return [TextContent(type="text", text=json.dumps({"sorted": sorted_versions}))]
            if name == "latest_version":
                versions = args["versions"]
                latest = max(versions, key=lambda v: semver.Version.parse(v))
                return [TextContent(type="text", text=json.dumps({"latest": latest}))]
            if name == "version_diff":
                v1 = semver.Version.parse(args["v1"])
                v2 = semver.Version.parse(args["v2"])
                if v1.major != v2.major:
                    diff = "major"
                elif v1.minor != v2.minor:
                    diff = "minor"
                elif v1.patch != v2.patch:
                    diff = "patch"
                elif v1.prerelease != v2.prerelease:
                    diff = "prerelease"
                else:
                    diff = "identical"
                return [TextContent(type="text", text=json.dumps({"diff": diff, "v1": str(v1), "v2": str(v2)}))]
            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = SemverServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
