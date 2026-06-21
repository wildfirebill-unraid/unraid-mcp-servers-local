import json
import os
from pathlib import Path

import qrcode
import qrcode.image.svg
from PIL import Image
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class QrcodeServer(Server):
    def __init__(self):
        super().__init__("qrcode")
        self._init_env()

    def _init_env(self):
        self._output_path = os.environ.get("QRCODE_PATH", os.getcwd())
        Path(self._output_path).mkdir(parents=True, exist_ok=True)

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="generate_qrcode",
                description="Generate a QR code PNG image",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "Data to encode in QR code"},
                        "version": {"type": "integer", "description": "QR code version (1-40)", "default": 1},
                        "box_size": {"type": "integer", "description": "Size of each box in pixels", "default": 10},
                        "border": {"type": "integer", "description": "Width of border (boxes)", "default": 4},
                    },
                    "required": ["data"],
                },
            ),
            Tool(
                name="generate_svg",
                description="Generate a QR code as SVG",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "Data to encode"},
                        "scale": {"type": "integer", "description": "Scale factor", "default": 1},
                    },
                    "required": ["data"],
                },
            ),
            Tool(
                name="generate_wifi_qr",
                description="Generate a WiFi configuration QR code",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ssid": {"type": "string", "description": "WiFi network name"},
                        "password": {"type": "string", "description": "WiFi password"},
                        "encryption": {"type": "string", "description": "Encryption type (WPA/WEP/nopass)", "enum": ["WPA", "WEP", "nopass"], "default": "WPA"},
                    },
                    "required": ["ssid", "password"],
                },
            ),
            Tool(
                name="generate_vcard_qr",
                description="Generate a vCard QR code",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Contact name"},
                        "phone": {"type": "string", "description": "Phone number"},
                        "email": {"type": "string", "description": "Email address"},
                        "org": {"type": "string", "description": "Organization"},
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="read_qrcode",
                description="Read/decode a QR code from an image file",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to QR code image file"},
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="qr_info",
                description="Get metadata about a QR code image file",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to QR code image file"},
                    },
                    "required": ["path"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "generate_qrcode":
                return [await self._generate_qrcode(args)]
            if name == "generate_svg":
                return [await self._generate_svg(args)]
            if name == "generate_wifi_qr":
                return [await self._generate_wifi_qr(args)]
            if name == "generate_vcard_qr":
                return [await self._generate_vcard_qr(args)]
            if name == "read_qrcode":
                return [await self._read_qrcode(args)]
            if name == "qr_info":
                return [await self._qr_info(args)]
            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def _generate_qrcode(self, args: dict) -> TextContent:
        data = args["data"]
        version = int(args.get("version", 1))
        box_size = int(args.get("box_size", 10))
        border = int(args.get("border", 4))
        qr = qrcode.QRCode(version=version, box_size=box_size, border=border)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        filename = f"qrcode_{hash(data) & 0xFFFFFFFF}.png"
        filepath = os.path.join(self._output_path, filename)
        img.save(filepath)
        return TextContent(type="text", text=json.dumps({"path": filepath, "data": data}))

    async def _generate_svg(self, args: dict) -> TextContent:
        data = args["data"]
        scale = int(args.get("scale", 1))
        factory = qrcode.image.svg.SvgImage
        img = qrcode.make(data, image_factory=factory, box_size=scale)
        filename = f"qrcode_{hash(data) & 0xFFFFFFFF}.svg"
        filepath = os.path.join(self._output_path, filename)
        img.save(filepath)
        return TextContent(type="text", text=json.dumps({"path": filepath, "data": data}))

    async def _generate_wifi_qr(self, args: dict) -> TextContent:
        ssid = args["ssid"]
        password = args.get("password", "")
        encryption = args.get("encryption", "WPA")
        wifi_string = f"WIFI:T:{encryption};S:{ssid};P:{password};;"
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(wifi_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        filename = f"wifi_{ssid.replace(' ', '_')}.png"
        filepath = os.path.join(self._output_path, filename)
        img.save(filepath)
        return TextContent(type="text", text=json.dumps({"path": filepath, "ssid": ssid}))

    async def _generate_vcard_qr(self, args: dict) -> TextContent:
        name = args["name"]
        phone = args.get("phone", "")
        email = args.get("email", "")
        org = args.get("org", "")
        vcard = "BEGIN:VCARD\nVERSION:3.0\n"
        vcard += f"FN:{name}\nN:{name};;;\n"
        if phone:
            vcard += f"TEL:{phone}\n"
        if email:
            vcard += f"EMAIL:{email}\n"
        if org:
            vcard += f"ORG:{org}\n"
        vcard += "END:VCARD"
        qr = qrcode.QRCode(version=2, box_size=10, border=4)
        qr.add_data(vcard)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        filename = f"vcard_{name.replace(' ', '_')}.png"
        filepath = os.path.join(self._output_path, filename)
        img.save(filepath)
        return TextContent(type="text", text=json.dumps({"path": filepath, "name": name}))

    async def _read_qrcode(self, args: dict) -> TextContent:
        return TextContent(type="text", text=json.dumps({"message": "QR code reading requires pyzbar library"}))

    async def _qr_info(self, args: dict) -> TextContent:
        path = args["path"]
        img = Image.open(path)
        info = {
            "path": path,
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "format": img.format,
            "size_bytes": os.path.getsize(path),
        }
        return TextContent(type="text", text=json.dumps(info))

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = QrcodeServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
