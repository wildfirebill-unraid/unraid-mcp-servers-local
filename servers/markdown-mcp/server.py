import os
import json
import re
from pathlib import Path
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio

server = Server("markdown-mcp")

BASE_PATH = Path(os.environ.get("MARKDOWN_PATH", "/data")).resolve()

def safe_path(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = BASE_PATH / p
    return p.resolve()

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="md_to_html",
            description="Convert Markdown text to HTML",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Markdown text to convert"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="md_to_text",
            description="Strip markdown formatting to plain text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Markdown text"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="md_toc",
            description="Generate a table of contents from markdown headings",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Markdown text"},
                    "max_level": {"type": "integer", "description": "Max heading level to include (default 3)"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="md_render_file",
            description="Convert a markdown file to an HTML file",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to markdown file"},
                    "output": {"type": "string", "description": "Output path for HTML (optional)"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="md_extract_links",
            description="Extract all links from markdown text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Markdown text"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="md_extract_code",
            description="Extract all code blocks from markdown text",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Markdown text"}
                },
                "required": ["text"]
            }
        ),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "md_to_html":
        import markdown
        html = markdown.markdown(arguments["text"], extensions=["fenced_code", "tables", "codehilite"])
        result = json.dumps({"html": html})
    elif name == "md_to_text":
        text = arguments["text"]
        text = re.sub(r'#{1,6}\s+', '', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        text = re.sub(r'!\[.*?\]\(.+?\)', '', text)
        text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*>\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'---', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        result = json.dumps({"text": text.strip()})
    elif name == "md_toc":
        text = arguments["text"]
        max_level = arguments.get("max_level", 3)
        toc_lines = []
        for line in text.splitlines():
            m = re.match(r'^(#{1,6})\s+(.+)$', line)
            if m:
                level = len(m.group(1))
                if level <= max_level:
                    title = m.group(2).strip()
                    slug = re.sub(r'[^\w\s-]', '', title).lower().replace(' ', '-')
                    indent = "  " * (level - 1)
                    toc_lines.append(f"{indent}- [{title}](#{slug})")
        result = json.dumps({"toc": "\n".join(toc_lines), "entries": len(toc_lines)})
    elif name == "md_render_file":
        import markdown
        filepath = safe_path(arguments["path"])
        md_text = filepath.read_text(encoding="utf-8")
        html = markdown.markdown(md_text, extensions=["fenced_code", "tables", "codehilite"])
        full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{filepath.stem}</title></head><body>{html}</body></html>"
        if arguments.get("output"):
            out_path = safe_path(arguments["output"])
        else:
            out_path = filepath.with_suffix(".html")
        out_path.write_text(full_html, encoding="utf-8")
        result = json.dumps({"path": str(out_path), "size": len(full_html)})
    elif name == "md_extract_links":
        text = arguments["text"]
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text)
        result = json.dumps({"links": [{"text": t, "url": u} for t, u in links], "count": len(links)})
    elif name == "md_extract_code":
        text = arguments["text"]
        blocks = re.findall(r'```(\w*)\n(.*?)```', text, re.DOTALL)
        code_blocks = []
        for lang, code in blocks:
            code_blocks.append({"language": lang if lang else "unknown", "code": code.strip()})
        inline = re.findall(r'`([^`]+)`', text)
        result = json.dumps({"code_blocks": code_blocks, "inline_code": inline,
                             "block_count": len(code_blocks), "inline_count": len(inline)})
    else:
        raise ValueError(f"Unknown tool: {name}")
    return [TextContent(type="text", text=result)]

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="markdown-mcp",
                server_version="1.0.0",
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
