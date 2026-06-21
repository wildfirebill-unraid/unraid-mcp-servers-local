import json
import random
import math
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

LOREM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit",
    "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore",
    "magna", "aliqua", "enim", "ad", "minim", "veniam", "quis", "nostrud",
    "exercitation", "ullamco", "laboris", "nisi", "ut", "aliquip", "ex", "ea",
    "commodo", "consequat", "duis", "aute", "irure", "dolor", "in", "reprehenderit",
    "voluptate", "velit", "esse", "cillum", "dolore", "eu", "fugiat", "nulla",
    "pariatur", "excepteur", "sint", "occaecat", "cupidatat", "non", "proident",
    "sunt", "in", "culpa", "qui", "officia", "deserunt", "mollit", "anim", "id",
    "est", "laborum", "fusce", "dapibus", "tellus", "ac", "cursus", "commodo",
    "tortor", "mauris", "condimentum", "nibh", "ut", "fermentum", "massa", "justo",
    "vitae", "erat", "donec", "ullamcorper", "nulla", "non", "metus", "auctor",
    "fringilla", "vestibulum", "ante", "ipsum", "primis", "in", "faucibus", "orci",
    "luctus", "et", "ultrices", "posuere", "cubilia", "curae", "maecenas", "tempus",
    "tellus", "eget", "condimentum", "rhoncus", "sem", "quam", "semper", "libero",
    "sit", "amet", "adipiscing", "sem", "neque", "sed", "ipsum", "nam", "quam",
    "nunc", "blandit", "vel", "luctus", "pulvinar", "hendrerit", "id", "lorem",
    "vivamus", "elementum", "semper", "nisi", "aenean", "vulputate", "eleifend",
    "tellus", "auctor", "ullamcorper", "faucibus", "interdum", "posuere", "lectus",
    "suspendisse", "potenti", "nullam", "porttitor", "lacus", "laoreet", "non",
    "arcu", "tortor", "pellentesque", "habitant", "morbi", "tristique", "senectus",
    "netus", "malesuada", "fames", "ac", "turpis", "egestas", "integer", "eget",
    "aliquet", "nibh", "praesent", "tristique", "magna", "sit", "amet", "purus",
    "gravida", "quis", "blandit", "turpis", "cursus", "in", "hac", "habitasse",
    "platea", "dictumst", "quisque", "sagittis", "purus", "sit", "amet", "volutpat",
    "consequat", "mauris", "nunc", "congue", "nisi", "vitae", "suscipit", "tellus",
    "mauris", "a", "diam", "maecenas", "sed", "enim", "ut", "sem", "viverra",
    "aliquet", "eget", "sit", "amet", "tellus", "cras", "adipiscing", "enim",
    "eu", "turpis", "egestas", "pretium", "aenean", "pharetra", "magna", "ac",
    "placerat", "vestibulum", "lectus", "mauris", "ultrices", "eros", "in",
    "cursus", "turpis", "massa", "tincidunt", "dui", "ut", "ornare", "lectus",
    "sit", "amet", "est", "placerat", "in", "egestas", "erat", "imperdiet",
]

class LoremServer(Server):
    def __init__(self):
        super().__init__("lorem")

    def _random_words(self, count: int) -> list[str]:
        return [random.choice(LOREM_WORDS) for _ in range(count)]

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="generate_words", description="Generate N random lorem ipsum words", inputSchema={"type": "object", "properties": {"count": {"type": "integer", "description": "Number of words to generate", "minimum": 1, "default": 10}}, "required": ["count"]}),
            Tool(name="generate_sentences", description="Generate N lorem ipsum sentences", inputSchema={"type": "object", "properties": {"count": {"type": "integer", "description": "Number of sentences to generate", "minimum": 1, "default": 3}}, "required": ["count"]}),
            Tool(name="generate_paragraphs", description="Generate N lorem ipsum paragraphs", inputSchema={"type": "object", "properties": {"count": {"type": "integer", "description": "Number of paragraphs to generate", "minimum": 1, "default": 2}}, "required": ["count"]}),
            Tool(name="lorem_bytes", description="Generate approximately N bytes of lorem ipsum text", inputSchema={"type": "object", "properties": {"size": {"type": "integer", "description": "Target size in bytes", "minimum": 1, "default": 1024}}, "required": ["size"]}),
            Tool(name="generate_custom", description="Generate custom lorem text using a provided list of words", inputSchema={"type": "object", "properties": {"words": {"type": "array", "items": {"type": "string"}, "description": "Custom list of words to use"}, "count": {"type": "integer", "description": "Number of words to generate", "default": 20}, "format": {"type": "string", "description": "Output format: 'words', 'sentence', or 'paragraph'", "default": "sentence"}}, "required": ["words"]}),
            Tool(name="format_text", description="Word-wrap text to a specified width", inputSchema={"type": "object", "properties": {"text": {"type": "string", "description": "Text to wrap"}, "width": {"type": "integer", "description": "Maximum line width", "default": 72, "minimum": 20}}, "required": ["text"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "generate_words":
                count = args.get("count", 10)
                words = self._random_words(count)
                return [TextContent(type="text", text=" ".join(words))]

            elif name == "generate_sentences":
                count = args.get("count", 3)
                sentences = []
                for _ in range(count):
                    n_words = random.randint(5, 15)
                    words = self._random_words(n_words)
                    sentence = words[0].capitalize() + " " + " ".join(words[1:]) + "."
                    sentences.append(sentence)
                return [TextContent(type="text", text=" ".join(sentences))]

            elif name == "generate_paragraphs":
                count = args.get("count", 2)
                paragraphs = []
                for _ in range(count):
                    n_sentences = random.randint(3, 8)
                    sentences = []
                    for _ in range(n_sentences):
                        n_words = random.randint(5, 15)
                        words = self._random_words(n_words)
                        sentence = words[0].capitalize() + " " + " ".join(words[1:]) + "."
                        sentences.append(sentence)
                    paragraphs.append(" ".join(sentences))
                return [TextContent(type="text", text="\n\n".join(paragraphs))]

            elif name == "lorem_bytes":
                target = args.get("size", 1024)
                output = []
                current_len = 0
                while current_len < target:
                    n_sentences = random.randint(3, 8)
                    sentences = []
                    for _ in range(n_sentences):
                        n_words = random.randint(5, 15)
                        words = self._random_words(n_words)
                        sentence = words[0].capitalize() + " " + " ".join(words[1:]) + "."
                        sentences.append(sentence)
                    para = " ".join(sentences)
                    output.append(para)
                    current_len = sum(len(p) for p in output) + 2 * len(output)
                text = "\n\n".join(output)
                if len(text) > target:
                    text = text[:target].rsplit(" ", 1)[0]
                return [TextContent(type="text", text=text)]

            elif name == "generate_custom":
                word_list = args["words"]
                count = args.get("count", 20)
                fmt = args.get("format", "sentence")
                chosen = [random.choice(word_list) for _ in range(count)]
                if fmt == "words":
                    result = " ".join(chosen)
                elif fmt == "sentence":
                    result = chosen[0].capitalize() + " " + " ".join(chosen[1:]) + "."
                elif fmt == "paragraph":
                    n = min(count, 6)
                    sentences = []
                    for s in range(n):
                        start = s * (count // n)
                        end = start + (count // n) if s < n - 1 else count
                        seg = chosen[start:end]
                        if seg:
                            sentence = seg[0].capitalize() + " " + " ".join(seg[1:]) + "."
                            sentences.append(sentence)
                    result = " ".join(sentences)
                else:
                    result = " ".join(chosen)
                return [TextContent(type="text", text=result)]

            elif name == "format_text":
                text = args["text"]
                width = args.get("width", 72)
                words = text.split()
                lines = []
                current = []
                current_len = 0
                for w in words:
                    if current_len + len(w) + len(current) > width:
                        lines.append(" ".join(current))
                        current = [w]
                        current_len = len(w)
                    else:
                        current.append(w)
                        current_len += len(w)
                if current:
                    lines.append(" ".join(current))
                return [TextContent(type="text", text="\n".join(lines))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    server = LoremServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
