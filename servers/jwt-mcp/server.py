import json
from datetime import datetime, timedelta, timezone

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
import jwt


class JwtServer(Server):
    SUPPORTED_ALGORITHMS = ["HS256", "HS384", "HS512"]

    def __init__(self):
        super().__init__("jwt")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="encode_jwt", description="Create a signed JWT token",
                 inputSchema={"type": "object", "properties": {
                     "payload_json": {"type": "string", "description": "JSON payload to encode in the token"},
                     "secret": {"type": "string", "description": "Secret key for HMAC signing"},
                     "algorithm": {"type": "string", "description": "HMAC algorithm", "enum": self.SUPPORTED_ALGORITHMS, "default": "HS256"}
                 }, "required": ["payload_json", "secret"]}),
            Tool(name="decode_jwt", description="Decode and verify a JWT token",
                 inputSchema={"type": "object", "properties": {
                     "token": {"type": "string", "description": "JWT token string"},
                     "secret": {"type": "string", "description": "Secret key for verification"},
                     "algorithms": {"type": "string", "description": "JSON array of algorithms to try", "default": '["HS256"]'}
                 }, "required": ["token", "secret"]}),
            Tool(name="verify_jwt", description="Verify a JWT signature without returning payload",
                 inputSchema={"type": "object", "properties": {
                     "token": {"type": "string", "description": "JWT token string"},
                     "secret": {"type": "string", "description": "Secret key for verification"},
                     "algorithms": {"type": "string", "description": "JSON array of algorithms to try", "default": '["HS256"]'}
                 }, "required": ["token", "secret"]}),
            Tool(name="parse_jwt", description="Decode header and payload without signature verification",
                 inputSchema={"type": "object", "properties": {
                     "token": {"type": "string", "description": "JWT token string"}
                 }, "required": ["token"]}),
            Tool(name="list_algorithms", description="List supported HMAC algorithms",
                 inputSchema={"type": "object", "properties": {}}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "encode_jwt":
                payload = json.loads(args["payload_json"])
                secret = args["secret"]
                algorithm = args.get("algorithm", "HS256")
                if algorithm not in self.SUPPORTED_ALGORITHMS:
                    raise ValueError(f"Unsupported algorithm: {algorithm}. Choose from: {self.SUPPORTED_ALGORITHMS}")
                token = jwt.encode(payload, secret, algorithm=algorithm)
                return [TextContent(type="text", text=token)]

            if name == "decode_jwt":
                token = args["token"]
                secret = args["secret"]
                algorithms = json.loads(args.get("algorithms", '["HS256"]'))
                decoded = jwt.decode(token, secret, algorithms=algorithms)
                return [TextContent(type="text", text=json.dumps(decoded, indent=2, default=str))]

            if name == "verify_jwt":
                token = args["token"]
                secret = args["secret"]
                algorithms = json.loads(args.get("algorithms", '["HS256"]'))
                decoded = jwt.decode(token, secret, algorithms=algorithms)
                return [TextContent(type="text", text=json.dumps({"valid": True, "payload": decoded}, indent=2, default=str))]

            if name == "parse_jwt":
                token = args["token"]
                header = jwt.get_unverified_header(token)
                payload = jwt.decode(token, options={"verify_signature": False})
                return [TextContent(type="text", text=json.dumps({"header": header, "payload": payload}, indent=2, default=str))]

            if name == "list_algorithms":
                return [TextContent(type="text", text=json.dumps({"supported_algorithms": self.SUPPORTED_ALGORITHMS}, indent=2))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = JwtServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
