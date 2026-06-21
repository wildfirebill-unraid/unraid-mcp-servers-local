import json
import base64
import os

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
import pyotp


class OtpServer(Server):
    SUPPORTED_ALGORITHMS = ["SHA1", "SHA256", "SHA512"]

    def __init__(self):
        super().__init__("otp")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="generate_totp", description="Generate current TOTP code",
                 inputSchema={"type": "object", "properties": {
                     "secret": {"type": "string", "description": "Base32 encoded secret key"}
                 }, "required": ["secret"]}),
            Tool(name="verify_totp", description="Verify a TOTP code within valid time window",
                 inputSchema={"type": "object", "properties": {
                     "secret": {"type": "string", "description": "Base32 encoded secret key"},
                     "code": {"type": "string", "description": "6-digit TOTP code to verify"}
                 }, "required": ["secret", "code"]}),
            Tool(name="generate_hotp", description="Generate HOTP code for a given counter",
                 inputSchema={"type": "object", "properties": {
                     "secret": {"type": "string", "description": "Base32 encoded secret key"},
                     "counter": {"type": "integer", "description": "Counter value"}
                 }, "required": ["secret", "counter"]}),
            Tool(name="verify_hotp", description="Verify an HOTP code for a given counter",
                 inputSchema={"type": "object", "properties": {
                     "secret": {"type": "string", "description": "Base32 encoded secret key"},
                     "code": {"type": "string", "description": "HOTP code to verify"},
                     "counter": {"type": "integer", "description": "Counter value"}
                 }, "required": ["secret", "code", "counter"]}),
            Tool(name="generate_secret", description="Generate a new random base32 secret",
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="list_algorithms", description="List supported OTP algorithms",
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="remaining_time", description="Get seconds remaining before current TOTP changes",
                 inputSchema={"type": "object", "properties": {
                     "secret": {"type": "string", "description": "Base32 encoded secret key"}
                 }, "required": ["secret"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "generate_totp":
                totp = pyotp.TOTP(args["secret"])
                code = totp.now()
                return [TextContent(type="text", text=code)]

            if name == "verify_totp":
                totp = pyotp.TOTP(args["secret"])
                valid = totp.verify(args["code"])
                return [TextContent(type="text", text=json.dumps({"valid": valid}))]

            if name == "generate_hotp":
                hotp = pyotp.HOTP(args["secret"])
                code = hotp.at(args["counter"])
                return [TextContent(type="text", text=code)]

            if name == "verify_hotp":
                hotp = pyotp.HOTP(args["secret"])
                valid = hotp.verify(args["code"], args["counter"])
                return [TextContent(type="text", text=json.dumps({"valid": valid}))]

            if name == "generate_secret":
                secret = pyotp.random_base32()
                return [TextContent(type="text", text=secret)]

            if name == "list_algorithms":
                return [TextContent(type="text", text=json.dumps({"supported_algorithms": self.SUPPORTED_ALGORITHMS}, indent=2))]

            if name == "remaining_time":
                totp = pyotp.TOTP(args["secret"])
                interval = totp.interval
                import time
                now = int(time.time())
                remaining = interval - (now % interval)
                return [TextContent(type="text", text=str(remaining))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = OtpServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
