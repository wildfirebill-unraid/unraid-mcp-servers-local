import json

from lingua import LanguageDetectorBuilder, Language
from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class LanguageDetectServer(Server):
    def __init__(self):
        super().__init__("language-detect")
        self._detector = LanguageDetectorBuilder.from_all_languages().build()
        self._all_languages = list(Language)

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="detect_language",
                description="Detect the language of a text",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to analyze"},
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="detect_languages",
                description="Detect multiple possible languages with confidence scores",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to analyze"},
                        "count": {"type": "integer", "description": "Number of top languages to return", "default": 5},
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="supported_languages",
                description="List all languages supported by the detector",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="text_analysis",
                description="Detailed language analysis with confidence scores for all detected languages",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to analyze"},
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="batch_detect",
                description="Detect language for multiple texts at once (JSON array of strings)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "texts": {"type": "array", "items": {"type": "string"}, "description": "Array of texts to analyze"},
                    },
                    "required": ["texts"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "detect_language":
                text = args["text"]
                lang = self._detector.detect_language_of(text)
                result = {"language": lang.name if lang else None, "text": text[:200]}
                return [TextContent(type="text", text=json.dumps(result))]
            if name == "detect_languages":
                text = args["text"]
                count = int(args.get("count", 5))
                confidences = self._detector.compute_language_confidence_values(text)
                results = []
                for ci in confidences[:count]:
                    results.append({"language": ci.language.name, "confidence": round(ci.value, 6)})
                return [TextContent(type="text", text=json.dumps({"detections": results, "text": text[:200]}))]
            if name == "supported_languages":
                langs = [lang.name for lang in self._all_languages]
                return [TextContent(type="text", text=json.dumps({"languages": langs, "count": len(langs)}))]
            if name == "text_analysis":
                text = args["text"]
                confidences = self._detector.compute_language_confidence_values(text)
                results = []
                for ci in confidences:
                    results.append({"language": ci.language.name, "confidence": round(ci.value, 6)})
                return [TextContent(type="text", text=json.dumps({"analysis": results, "text": text[:200]}))]
            if name == "batch_detect":
                texts = args["texts"]
                results = []
                for text in texts:
                    lang = self._detector.detect_language_of(text)
                    results.append({"text": text[:200], "language": lang.name if lang else None})
                return [TextContent(type="text", text=json.dumps({"results": results}))]
            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = LanguageDetectServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
