import json
import math
import itertools

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class CipherServer(Server):
    def __init__(self):
        super().__init__("cipher")

    @staticmethod
    def _caesar(text: str, shift: int, mode: str) -> str:
        shift = shift % 26
        if mode == "decrypt":
            shift = -shift
        result = []
        for ch in text:
            if "a" <= ch <= "z":
                result.append(chr((ord(ch) - 97 + shift) % 26 + 97))
            elif "A" <= ch <= "Z":
                result.append(chr((ord(ch) - 65 + shift) % 26 + 65))
            else:
                result.append(ch)
        return "".join(result)

    @staticmethod
    def _vigenere(text: str, key: str, mode: str) -> str:
        if not key:
            raise ValueError("Key cannot be empty")
        key = key.upper()
        result = []
        key_idx = 0
        for ch in text:
            if "A" <= ch <= "Z":
                shift = ord(key[key_idx % len(key)]) - 65
                if mode == "decrypt":
                    shift = -shift
                result.append(chr((ord(ch) - 65 + shift) % 26 + 65))
                key_idx += 1
            elif "a" <= ch <= "z":
                shift = ord(key[key_idx % len(key)]) - 65
                if mode == "decrypt":
                    shift = -shift
                result.append(chr((ord(ch) - 97 + shift) % 26 + 97))
                key_idx += 1
            else:
                result.append(ch)
        return "".join(result)

    @staticmethod
    def _atbash(text: str) -> str:
        result = []
        for ch in text:
            if "a" <= ch <= "z":
                result.append(chr(219 - ord(ch)))
            elif "A" <= ch <= "Z":
                result.append(chr(155 - ord(ch)))
            else:
                result.append(ch)
        return "".join(result)

    @staticmethod
    def _rot(text: str, rotation: int) -> str:
        rotation = rotation % 95
        result = []
        for ch in text:
            code = ord(ch)
            if 32 <= code <= 126:
                result.append(chr((code - 32 + rotation) % 95 + 32))
            else:
                result.append(ch)
        return "".join(result)

    @staticmethod
    def _xor(text: str, key: str) -> str:
        if not key:
            raise ValueError("Key cannot be empty")
        key_bytes = key.encode("utf-8")
        text_bytes = text.encode("utf-8")
        result = bytes(a ^ key_bytes[i % len(key_bytes)] for i, a in enumerate(text_bytes))
        return result.hex()

    @staticmethod
    def _substitution(text: str, key: str, mode: str) -> str:
        if len(key) != 26 or not key.isalpha():
            raise ValueError("Key must be 26 unique alphabetic characters")
        key = key.upper()
        key_set = set(key)
        if len(key_set) != 26:
            raise ValueError("Key must contain exactly 26 unique letters")
        normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        result = []
        for ch in text:
            if "a" <= ch <= "z":
                if mode == "encrypt":
                    result.append(key[ord(ch) - 97].lower())
                else:
                    idx = key.index(ch.upper())
                    result.append(normal[idx].lower())
            elif "A" <= ch <= "Z":
                if mode == "encrypt":
                    result.append(key[ord(ch) - 65])
                else:
                    idx = key.index(ch)
                    result.append(normal[idx])
            else:
                result.append(ch)
        return "".join(result)

    @staticmethod
    def _transposition(text: str, key: int, mode: str) -> str:
        if key < 2:
            raise ValueError("Key (number of columns) must be >= 2")
        if mode == "encrypt":
            n = math.ceil(len(text) / key)
            padded = text.ljust(n * key, " ")
            rows = [padded[i:i+key] for i in range(0, len(padded), key)]
            result = []
            for col in range(key):
                for row in rows:
                    result.append(row[col])
            return "".join(result).rstrip()
        else:
            n = key
            cols = math.ceil(len(text) / n)
            total = cols * n
            padded = text.ljust(total, " ")
            rows = [padded[i:i+n] for i in range(0, len(padded), n)]
            result = []
            for col in range(n):
                for row in rows:
                    result.append(row[col])
            return "".join(result).rstrip()

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="caesar_cipher", description="Caesar cipher encrypt/decrypt", inputSchema={"type":"object","properties":{"text":{"type":"string","description":"Text to process"},"shift":{"type":"integer","description":"Shift amount (1-25)","default":3},"mode":{"type":"string","description":"encrypt or decrypt","default":"encrypt","enum":["encrypt","decrypt"]}},"required":["text"]}),
            Tool(name="vigenere_cipher", description="Vigenère cipher encrypt/decrypt", inputSchema={"type":"object","properties":{"text":{"type":"string","description":"Text to process"},"key":{"type":"string","description":"Encryption key"},"mode":{"type":"string","description":"encrypt or decrypt","default":"encrypt","enum":["encrypt","decrypt"]}},"required":["text","key"]}),
            Tool(name="atbash_cipher", description="Atbash cipher (reverse alphabet mapping)", inputSchema={"type":"object","properties":{"text":{"type":"string","description":"Text to transform"}},"required":["text"]}),
            Tool(name="rot_cipher", description="ROT cipher (printable ASCII rotation, e.g. ROT13, ROT47)", inputSchema={"type":"object","properties":{"text":{"type":"string","description":"Text to rotate"},"rotation":{"type":"integer","description":"Rotation amount","default":13}},"required":["text"]}),
            Tool(name="xor_cipher", description="XOR cipher with key byte (returns hex)", inputSchema={"type":"object","properties":{"text":{"type":"string","description":"Text to XOR"},"key":{"type":"string","description":"XOR key"}},"required":["text","key"]}),
            Tool(name="substitution_cipher", description="Simple substitution cipher (key must be 26 unique letters)", inputSchema={"type":"object","properties":{"text":{"type":"string","description":"Text to process"},"key":{"type":"string","description":"26-character substitution alphabet"},"mode":{"type":"string","description":"encrypt or decrypt","default":"encrypt","enum":["encrypt","decrypt"]}},"required":["text","key"]}),
            Tool(name="transposition_cipher", description="Columnar transposition cipher", inputSchema={"type":"object","properties":{"text":{"type":"string","description":"Text to process"},"key":{"type":"integer","description":"Number of columns","default":5},"mode":{"type":"string","description":"encrypt or decrypt","default":"encrypt","enum":["encrypt","decrypt"]}},"required":["text"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        if name == "caesar_cipher":
            text = args.get("text", "")
            shift = args.get("shift", 3)
            mode = args.get("mode", "encrypt")
            result = self._caesar(text, shift, mode)
            return [TextContent(type="text", text=json.dumps({"result": result}))]

        if name == "vigenere_cipher":
            text = args.get("text", "")
            key = args.get("key", "")
            mode = args.get("mode", "encrypt")
            result = self._vigenere(text, key, mode)
            return [TextContent(type="text", text=json.dumps({"result": result}))]

        if name == "atbash_cipher":
            text = args.get("text", "")
            result = self._atbash(text)
            return [TextContent(type="text", text=json.dumps({"result": result}))]

        if name == "rot_cipher":
            text = args.get("text", "")
            rotation = args.get("rotation", 13)
            result = self._rot(text, rotation)
            return [TextContent(type="text", text=json.dumps({"result": result}))]

        if name == "xor_cipher":
            text = args.get("text", "")
            key = args.get("key", "")
            result = self._xor(text, key)
            return [TextContent(type="text", text=json.dumps({"result": result}))]

        if name == "substitution_cipher":
            text = args.get("text", "")
            key = args.get("key", "")
            mode = args.get("mode", "encrypt")
            result = self._substitution(text, key, mode)
            return [TextContent(type="text", text=json.dumps({"result": result}))]

        if name == "transposition_cipher":
            text = args.get("text", "")
            key = args.get("key", 5)
            mode = args.get("mode", "encrypt")
            if not isinstance(key, int):
                key = int(key)
            result = self._transposition(text, key, mode)
            return [TextContent(type="text", text=json.dumps({"result": result}))]

        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = CipherServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
