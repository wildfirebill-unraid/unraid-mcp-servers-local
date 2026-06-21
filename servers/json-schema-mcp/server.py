import json
from typing import Any

from jsonschema import validate, Draft202012Validator, ValidationError
from jsonschema import exceptions as js_exc
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


def _load_json(s: str) -> Any:
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


class JsonSchemaServer(Server):
    def __init__(self):
        super().__init__("json-schema-server")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="validate_json",
                description="Validate a JSON instance against a JSON Schema",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema_json": {
                            "type": "string",
                            "description": "JSON Schema as a string",
                        },
                        "instance_json": {
                            "type": "string",
                            "description": "JSON instance to validate",
                        },
                    },
                    "required": ["schema_json", "instance_json"],
                },
            ),
            Tool(
                name="generate_schema",
                description="Generate a JSON Schema from a sample JSON instance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instance_json": {
                            "type": "string",
                            "description": "Sample JSON instance",
                        }
                    },
                    "required": ["instance_json"],
                },
            ),
            Tool(
                name="lint_schema",
                description="Check a JSON Schema for common issues and best practices",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema_json": {
                            "type": "string",
                            "description": "JSON Schema as a string",
                        }
                    },
                    "required": ["schema_json"],
                },
            ),
            Tool(
                name="json_schema_to_markdown",
                description="Render a JSON Schema as human-readable Markdown",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema_json": {
                            "type": "string",
                            "description": "JSON Schema as a string",
                        }
                    },
                    "required": ["schema_json"],
                },
            ),
            Tool(
                name="check_compatibility",
                description="Check if schema2 is backward-compatible with schema1 (schema1 valid instances remain valid)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema1_json": {
                            "type": "string",
                            "description": "Older JSON Schema",
                        },
                        "schema2_json": {
                            "type": "string",
                            "description": "Newer JSON Schema to check",
                        },
                    },
                    "required": ["schema1_json", "schema2_json"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "validate_json":
            return await self._validate_json(args["schema_json"], args["instance_json"])
        if name == "generate_schema":
            return await self._generate_schema(args["instance_json"])
        if name == "lint_schema":
            return await self._lint_schema(args["schema_json"])
        if name == "json_schema_to_markdown":
            return await self._to_markdown(args["schema_json"])
        if name == "check_compatibility":
            return await self._check_compatibility(args["schema1_json"], args["schema2_json"])
        raise ValueError(f"Unknown tool: {name}")

    async def _validate_json(self, schema_json: str, instance_json: str) -> list[TextContent]:
        schema = _load_json(schema_json)
        instance = _load_json(instance_json)
        try:
            validate(instance=instance, schema=schema)
            return [TextContent(type="text", text=json.dumps({"valid": True}))]
        except ValidationError as e:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"valid": False, "error": e.message, "path": list(e.absolute_path)}
                    ),
                )
            ]

    async def _generate_schema(self, instance_json: str) -> list[TextContent]:
        instance = _load_json(instance_json)
        schema = self._infer_schema(instance)
        return [TextContent(type="text", text=json.dumps(schema, indent=2))]

    def _infer_schema(self, instance: Any) -> dict:
        if instance is None:
            return {"type": "null"}
        if isinstance(instance, bool):
            return {"type": "boolean"}
        if isinstance(instance, int):
            return {"type": "integer"}
        if isinstance(instance, float):
            return {"type": "number"}
        if isinstance(instance, str):
            return {"type": "string"}
        if isinstance(instance, list):
            if not instance:
                return {"type": "array"}
            item_schemas = [self._infer_schema(item) for item in instance]
            types = {json.dumps(s, sort_keys=True) for s in item_schemas}
            if len(types) == 1:
                return {"type": "array", "items": item_schemas[0]}
            return {"type": "array", "items": {"anyOf": [json.loads(t) for t in types]}}
        if isinstance(instance, dict):
            properties = {k: self._infer_schema(v) for k, v in instance.items()}
            return {"type": "object", "properties": properties, "required": list(properties.keys())}
        return {}

    async def _lint_schema(self, schema_json: str) -> list[TextContent]:
        schema = _load_json(schema_json)
        issues = []

        if not isinstance(schema, dict):
            issues.append({"severity": "error", "message": "Schema must be a JSON object"})
            return [TextContent(type="text", text=json.dumps({"issues": issues}, indent=2))]

        if "$schema" not in schema:
            issues.append({"severity": "warning", "message": "Missing $schema keyword"})
        if schema.get("type") not in ("object", "array", "string", "number", "integer", "boolean", "null", None):
            issues.append({"severity": "info", "message": "No top-level type specified"})
        if "additionalProperties" not in schema and schema.get("type") == "object":
            issues.append({"severity": "warning", "message": "Missing additionalProperties (defaults to true, allowing extra properties)"})

        try:
            Draft202012Validator.check_schema(schema)
        except js_exc.SchemaError as e:
            issues.append({"severity": "error", "message": f"Schema validation error: {e.message}"})

        return [TextContent(type="text", text=json.dumps({"issues": issues}, indent=2))]

    async def _to_markdown(self, schema_json: str) -> list[TextContent]:
        schema = _load_json(schema_json)
        lines = []
        title = schema.get("title", schema.get("$id", "JSON Schema"))
        lines.append(f"# {title}")
        if schema.get("description"):
            lines.append(f"\n{schema['description']}\n")
        lines.append(f"- **Type:** `{schema.get('type', 'any')}`")
        if schema.get("$schema"):
            lines.append(f"- **Schema:** `{schema['$schema']}`")
        if schema.get("default") is not None:
            lines.append(f"- **Default:** `{json.dumps(schema['default'])}`")
        lines.append("")
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        if props:
            lines.append("## Properties\n")
            lines.append("| Property | Type | Required | Description |")
            lines.append("|----------|------|----------|-------------|")
            for name, prop in props.items():
                ptype = prop.get("type", "any")
                req = "Yes" if name in required else "No"
                desc = prop.get("description", "")
                lines.append(f"| `{name}` | `{ptype}` | {req} | {desc} |")
        defs = schema.get("$defs", schema.get("definitions", {}))
        if defs:
            lines.append("\n## Definitions\n")
            for name, defn in defs.items():
                lines.append(f"### `{name}`")
                lines.append(f"- **Type:** `{defn.get('type', 'any')}`")
                if defn.get("description"):
                    lines.append(f"- {defn['description']}")
                lines.append("")
        return [TextContent(type="text", text="\n".join(lines))]

    async def _check_compatibility(self, schema1_json: str, schema2_json: str) -> list[TextContent]:
        schema1 = _load_json(schema1_json)
        schema2 = _load_json(schema2_json)
        issues = []

        def _all_of(validator, val, instance, schema):
            pass

        props1 = schema1.get("properties", {})
        props2 = schema2.get("properties", {})
        required1 = set(schema1.get("required", []))
        required2 = set(schema2.get("required", []))

        removed = required1 - required2
        if removed:
            issues.append({"type": "breaking", "message": f"Properties removed from required: {list(removed)}"})

        added_required = required2 - required1
        if added_required:
            for prop in added_required:
                default = props2.get(prop, {}).get("default")
                if default is None:
                    issues.append({"type": "breaking", "message": f"New required property without default: {prop}"})

        for prop in props1:
            if prop not in props2:
                issues.append({"type": "breaking", "message": f"Property removed: {prop}"})

        if not issues:
            issues.append({"type": "info", "message": "No breaking changes detected"})

        return [TextContent(type="text", text=json.dumps({"compatible": len([i for i in issues if i["type"] == "breaking"]) == 0, "issues": issues}, indent=2))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = JsonSchemaServer()
    async with stdio_server() as (read, write):
        await server.run(
            read, write, server.list_tools, server.call_tool,
            server.list_resources, server.read_resource,
        )

if __name__ == "__main__":
    anyio.run(main)
