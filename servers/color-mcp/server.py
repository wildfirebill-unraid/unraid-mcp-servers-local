import os
import json
import re
import random
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("color-mcp")

def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    h = s = 0
    l = (mx + mn) / 2
    if mx != mn:
        d = mx - mn
        s = d / (1 - abs(2 * l - 1))
        if mx == r:
            h = ((g - b) / d) % 6
        elif mx == g:
            h = (b - r) / d + 2
        else:
            h = (r - g) / d + 4
        h /= 6
    return (round(h * 360), round(s * 100), round(l * 100))

def hsl_to_hex(h: float, s: float, l: float) -> str:
    h, s, l = h / 360, s / 100, l / 100
    if s == 0:
        r = g = b = l
    else:
        def hue2rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue2rgb(p, q, h + 1/3)
        g = hue2rgb(p, q, h)
        b = hue2rgb(p, q, h - 1/3)
    return "#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255))

def luminance(hex_color: str) -> float:
    r, g, b = hex_to_rgb(hex_color)
    def ch(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="hex_to_rgb",
            description="Convert hex color (#FF8800 or #F80) to RGB",
            inputSchema={
                "type": "object",
                "properties": {
                    "hex_color": {"type": "string", "description": "Hex color code (e.g. #FF8800 or #F80)"}
                },
                "required": ["hex_color"]
            }
        ),
        Tool(
            name="rgb_to_hex",
            description="Convert RGB (0-255) to hex color",
            inputSchema={
                "type": "object",
                "properties": {
                    "r": {"type": "integer", "description": "Red value (0-255)"},
                    "g": {"type": "integer", "description": "Green value (0-255)"},
                    "b": {"type": "integer", "description": "Blue value (0-255)"}
                },
                "required": ["r", "g", "b"]
            }
        ),
        Tool(
            name="hex_to_hsl",
            description="Convert hex color to HSL values",
            inputSchema={
                "type": "object",
                "properties": {
                    "hex_color": {"type": "string", "description": "Hex color code"}
                },
                "required": ["hex_color"]
            }
        ),
        Tool(
            name="hsl_to_hex",
            description="Convert HSL values to hex color",
            inputSchema={
                "type": "object",
                "properties": {
                    "h": {"type": "number", "description": "Hue (0-360)"},
                    "s": {"type": "number", "description": "Saturation (0-100)"},
                    "l": {"type": "number", "description": "Lightness (0-100)"}
                },
                "required": ["h", "s", "l"]
            }
        ),
        Tool(
            name="blend_colors",
            description="Blend two hex colors by a ratio",
            inputSchema={
                "type": "object",
                "properties": {
                    "color1": {"type": "string", "description": "First hex color"},
                    "color2": {"type": "string", "description": "Second hex color"},
                    "ratio": {"type": "number", "description": "Blend ratio (0-1), default 0.5"}
                },
                "required": ["color1", "color2"]
            }
        ),
        Tool(
            name="contrast_ratio",
            description="Calculate WCAG contrast ratio between two colors",
            inputSchema={
                "type": "object",
                "properties": {
                    "color1": {"type": "string", "description": "First hex color"},
                    "color2": {"type": "string", "description": "Second hex color"}
                },
                "required": ["color1", "color2"]
            }
        ),
        Tool(
            name="color_scheme",
            description="Generate complementary, triadic, or analogous color scheme",
            inputSchema={
                "type": "object",
                "properties": {
                    "hex_color": {"type": "string", "description": "Base hex color"},
                    "scheme": {"type": "string", "description": "Scheme type: complementary, triadic, analogous"}
                },
                "required": ["hex_color", "scheme"]
            }
        ),
        Tool(
            name="random_palette",
            description="Generate a random color palette",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of colors (default 5)"}
                }
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "hex_to_rgb":
        r, g, b = hex_to_rgb(arguments["hex_color"])
        result = json.dumps({"r": r, "g": g, "b": b})
    elif name == "rgb_to_hex":
        result = hsl_to_hex(arguments["r"], arguments["g"], arguments["b"])
    elif name == "hex_to_hsl":
        r, g, b = hex_to_rgb(arguments["hex_color"])
        h, s, l = rgb_to_hsl(r, g, b)
        result = json.dumps({"h": h, "s": s, "l": l})
    elif name == "hsl_to_hex":
        result = hsl_to_hex(arguments["h"], arguments["s"], arguments["l"])
    elif name == "blend_colors":
        r1, g1, b1 = hex_to_rgb(arguments["color1"])
        r2, g2, b2 = hex_to_rgb(arguments["color2"])
        ratio = arguments.get("ratio", 0.5)
        r = round(r1 * (1 - ratio) + r2 * ratio)
        g = round(g1 * (1 - ratio) + g2 * ratio)
        b = round(b1 * (1 - ratio) + b2 * ratio)
        result = "#{:02X}{:02X}{:02X}".format(r, g, b)
    elif name == "contrast_ratio":
        l1 = luminance(arguments["color1"])
        l2 = luminance(arguments["color2"])
        lighter = max(l1, l2)
        darker = min(l1, l2)
        ratio = (lighter + 0.05) / (darker + 0.05)
        aa_large = ratio >= 3
        aa_normal = ratio >= 4.5
        aaa_normal = ratio >= 7
        result = json.dumps({"ratio": round(ratio, 2), "AA_large": aa_large, "AA_normal": aa_normal, "AAA_normal": aaa_normal})
    elif name == "color_scheme":
        h, s, l = rgb_to_hsl(*hex_to_rgb(arguments["hex_color"]))
        scheme = arguments["scheme"]
        colors = [arguments["hex_color"]]
        if scheme == "complementary":
            colors.append(hsl_to_hex((h + 180) % 360, s, l))
        elif scheme == "triadic":
            colors.append(hsl_to_hex((h + 120) % 360, s, l))
            colors.append(hsl_to_hex((h + 240) % 360, s, l))
        elif scheme == "analogous":
            colors.append(hsl_to_hex((h + 30) % 360, s, l))
            colors.append(hsl_to_hex((h + 60) % 360, s, l))
            colors.append(hsl_to_hex((h - 30) % 360, s, l))
        result = json.dumps({"scheme": scheme, "colors": colors})
    elif name == "random_palette":
        count = arguments.get("count", 5)
        colors = []
        for _ in range(count):
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            colors.append("#{:02X}{:02X}{:02X}".format(r, g, b))
        result = json.dumps({"colors": colors, "count": count})
    else:
        raise ValueError(f"Unknown tool: {name}")
    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="color-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
