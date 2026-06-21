import os
import json
import math
import re
import secrets
import string
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("password-mcp")

BASE_PATH = Path(os.environ.get("PASSWORD_MCP_PATH", "/data"))

COMMON_PATTERNS = [
    r"1234", r"password", r"qwerty", r"abc123", r"letmein",
    r"admin", r"welcome", r"monkey", r"dragon", r"master",
    r"(.)\1{3,}",  # repeated chars like aaaa
]

def _shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    freq = {}
    for c in text:
        freq[c] = freq.get(c, 0) + 1
    entropy = 0.0
    length = len(text)
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return round(entropy, 2)

def _estimate_crack_time(entropy_bits: float) -> str:
    guesses_per_second = 1e9
    combinations = 2 ** entropy_bits
    seconds = combinations / guesses_per_second
    if seconds < 1:
        return "instantly"
    if seconds < 60:
        return f"{int(seconds)} seconds"
    if seconds < 3600:
        return f"{int(seconds / 60)} minutes"
    if seconds < 86400:
        return f"{int(seconds / 3600)} hours"
    if seconds < 31536000:
        return f"{int(seconds / 86400)} days"
    if seconds < 31536000 * 100:
        return f"{int(seconds / 31536000)} years"
    return "centuries"

def _password_strength(password: str) -> dict:
    score = 0
    feedback = []
    length = len(password)

    if length >= 8:
        score += 10
    if length >= 12:
        score += 10
    if length >= 16:
        score += 10
    if length >= 20:
        score += 10

    has_upper = bool(re.search(r"[A-Z]", password))
    has_lower = bool(re.search(r"[a-z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_symbol = bool(re.search(r"[^a-zA-Z0-9]", password))

    char_types = sum([has_upper, has_lower, has_digit, has_symbol])
    score += char_types * 8

    if has_upper and has_lower:
        score += 5
    if has_digit:
        score += 5
    if has_symbol:
        score += 10

    for pattern in COMMON_PATTERNS:
        if re.search(pattern, password, re.IGNORECASE):
            score -= 20
            feedback.append("Contains common pattern")

    if len(set(password)) < length * 0.5:
        score -= 10
        feedback.append("Low character variety")

    if length < 8:
        feedback.append("Too short (minimum 8 characters)")
    if not has_upper:
        feedback.append("Missing uppercase letters")
    if not has_lower:
        feedback.append("Missing lowercase letters")
    if not has_digit:
        feedback.append("Missing digits")
    if not has_symbol:
        feedback.append("Missing symbols")

    score = max(0, min(100, score))
    entropy = _shannon_entropy(password)
    crack_time = _estimate_crack_time(entropy * 2)

    return {
        "score": score,
        "entropy_bits": entropy,
        "crack_time_estimate": crack_time,
        "feedback": feedback,
    }

def _generate_password(length: int = 20, upper: bool = True, digits: bool = True,
                       symbols: bool = True, exclude_similar: bool = False) -> str:
    chars = string.ascii_lowercase
    if upper:
        chars += string.ascii_uppercase
    if digits:
        chars += string.digits
    if symbols:
        chars += string.punctuation
    if exclude_similar:
        for c in "il1Lo0O":
            chars = chars.replace(c, "")
    if not chars:
        chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))

def _generate_passphrase(word_count: int = 5, separator: str = "-") -> str:
    word_list = [
        "correct", "horse", "battery", "staple", "whisper", "purple", "sunset",
        "mountain", "river", "forest", "ocean", "desert", "valley", "crystal",
        "thunder", "silver", "golden", "copper", "bronze", "steel", "stone",
        "flame", "frost", "storm", "breeze", "dawn", "dusk", "shadow", "light",
        "eagle", "falcon", "raven", "hawk", "dove", "wolf", "bear", "deer",
        "fox", "lion", "tiger", "puma", "swan", "heron", "crane", "rook",
        "rook", "knight", "bishop", "king", "queen", "pawn", "chess", "board",
        "amber", "azure", "coral", "emerald", "jade", "onyx", "ruby", "sapphire",
        "topaz", "garnet", "opal", "pearl", "jazz", "blues", "rock", "folk",
        "opera", "swing", "waltz", "rebel", "pilot", "captain", "doctor", "judge",
        "knight", "squire", "page", "chief", "major", "minor", "noble", "royal",
        "apple", "bread", "cream", "dance", "eagle", "flame", "grace", "heart",
        "ivory", "jewel", "knife", "lemon", " maple", "night", "ocean", "pearl",
        "queen", "river", "stone", "tiger", "unity", "vivid", "water", "youth",
    ]
    words = [secrets.choice(word_list) for _ in range(word_count)]
    return separator.join(words)

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="generate_password",
            description="Generate secure password",
            inputSchema={
                "type": "object",
                "properties": {
                    "length": {"type": "integer", "description": "Password length", "default": 20},
                    "include_uppercase": {"type": "boolean", "description": "Include uppercase letters", "default": True},
                    "include_digits": {"type": "boolean", "description": "Include digits", "default": True},
                    "include_symbols": {"type": "boolean", "description": "Include symbols", "default": True},
                    "exclude_similar": {"type": "boolean", "description": "Exclude similar chars (il1Lo0O)", "default": False},
                },
            },
        ),
        Tool(
            name="password_strength",
            description="Analyze password strength",
            inputSchema={
                "type": "object",
                "properties": {
                    "password": {"type": "string", "description": "Password to analyze"},
                },
                "required": ["password"],
            },
        ),
        Tool(
            name="generate_passphrase",
            description="Generate memorable passphrase",
            inputSchema={
                "type": "object",
                "properties": {
                    "word_count": {"type": "integer", "description": "Number of words", "default": 5},
                    "separator": {"type": "string", "description": "Word separator", "default": "-"},
                },
            },
        ),
        Tool(
            name="check_entropy",
            description="Calculate Shannon entropy of a string",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to analyze"},
                },
                "required": ["text"],
            },
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "generate_password":
        length = arguments.get("length", 20)
        upper = arguments.get("include_uppercase", True)
        digits = arguments.get("include_digits", True)
        symbols = arguments.get("include_symbols", True)
        exclude = arguments.get("exclude_similar", False)
        pw = _generate_password(length, upper, digits, symbols, exclude)
        entropy = _shannon_entropy(pw)
        strength = _password_strength(pw)
        result = json.dumps({
            "password": pw,
            "length": len(pw),
            "entropy_bits": entropy,
            "strength_score": strength["score"],
        }, indent=2)

    elif name == "password_strength":
        password = arguments["password"]
        analysis = _password_strength(password)
        result = json.dumps(analysis, indent=2)

    elif name == "generate_passphrase":
        word_count = arguments.get("word_count", 5)
        separator = arguments.get("separator", "-")
        phrase = _generate_passphrase(word_count, separator)
        result = json.dumps({
            "passphrase": phrase,
            "word_count": word_count,
        }, indent=2)

    elif name == "check_entropy":
        text = arguments["text"]
        entropy = _shannon_entropy(text)
        result = json.dumps({
            "text": text,
            "entropy_bits": entropy,
        }, indent=2)

    else:
        result = f"Unknown tool: {name}"

    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="password-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
