import sys
import json
import os
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


class WebhookServer(Server):
    def __init__(self):
        super().__init__("webhook")
        self._init_env()

    def _init_env(self):
        self._default_timeout = int(os.environ.get("WEBHOOK_TIMEOUT", "30"))

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="send_webhook", description="Send a webhook with custom method (POST/GET/PUT)",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "url": {"type": "string"},
                         "data_json": {"type": "string", "description": "JSON string payload"},
                         "method": {"type": "string", "enum": ["POST", "GET", "PUT"], "default": "POST"},
                         "headers_json": {"type": "string", "description": "Optional JSON string of custom headers"},
                     },
                     "required": ["url"],
                 }),
            Tool(name="send_json", description="Shorthand for POST JSON payload",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "url": {"type": "string"},
                         "data_json": {"type": "string", "description": "JSON string payload"},
                         "headers_json": {"type": "string", "description": "Optional JSON string of custom headers"},
                     },
                     "required": ["url", "data_json"],
                 }),
            Tool(name="send_form", description="Send form-encoded data via POST",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "url": {"type": "string"},
                         "data_json": {"type": "string", "description": "JSON string of form fields"},
                         "headers_json": {"type": "string", "description": "Optional JSON string of custom headers"},
                     },
                     "required": ["url", "data_json"],
                 }),
            Tool(name="verify_webhook", description="Check if a webhook endpoint is reachable",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "url": {"type": "string"},
                         "timeout": {"type": "number", "description": "Timeout in seconds"},
                     },
                     "required": ["url"],
                 }),
            Tool(name="webhook_info", description="GET a URL and return status code + response headers (no body)",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "url": {"type": "string"},
                     },
                     "required": ["url"],
                 }),
            Tool(name="send_batch", description="Batch send multiple JSON payloads to a URL sequentially",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "url": {"type": "string"},
                         "requests_json": {"type": "string", "description": "JSON array of payload strings"},
                     },
                     "required": ["url", "requests_json"],
                 }),
            Tool(name="webhook_log", description="Send a webhook and return full request + response details",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "url": {"type": "string"},
                         "data_json": {"type": "string", "description": "JSON string payload"},
                         "headers_json": {"type": "string", "description": "Optional JSON string of custom headers"},
                     },
                     "required": ["url", "data_json"],
                 }),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            import httpx

            if name in ("send_webhook", "send_json", "send_form", "webhook_log"):
                url = args["url"]
                method = args.get("method", "POST") if name == "send_webhook" else "POST"
                data_raw = args.get("data_json", "{}")
                headers_raw = args.get("headers_json", "{}")
                payload = json.loads(data_raw) if data_raw else {}
                headers = json.loads(headers_raw) if headers_raw else {}
                is_form = name == "send_form"

                async with httpx.AsyncClient(timeout=self._default_timeout) as client:
                    if name == "webhook_log":
                        req = client.build_request(method, url, json=payload, headers=headers)
                        resp = await client.send(req)
                        log = {
                            "request": {
                                "method": req.method,
                                "url": str(req.url),
                                "headers": dict(req.headers),
                                "body": payload,
                            },
                            "response": {
                                "status_code": resp.status_code,
                                "headers": dict(resp.headers),
                                "body": resp.text[:10000],
                            },
                        }
                        return [TextContent(type="text", text=json.dumps(log))]

                    if is_form:
                        resp = await client.post(url, data=payload, headers=headers)
                    else:
                        resp = await client.request(method, url, json=payload, headers=headers)

                    result = {
                        "status_code": resp.status_code,
                        "body": resp.text[:10000],
                    }
                    return [TextContent(type="text", text=json.dumps(result))]

            if name == "verify_webhook":
                url = args["url"]
                timeout = args.get("timeout", self._default_timeout)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    try:
                        resp = await client.head(url)
                        reachable = resp.status_code < 500
                    except Exception:
                        try:
                            resp = await client.get(url)
                            reachable = resp.status_code < 500
                        except Exception:
                            reachable = False
                    return [TextContent(type="text", text=json.dumps({
                        "reachable": reachable,
                        "url": url,
                    }))]

            if name == "webhook_info":
                url = args["url"]
                async with httpx.AsyncClient(timeout=self._default_timeout) as client:
                    resp = await client.get(url)
                    return [TextContent(type="text", text=json.dumps({
                        "status_code": resp.status_code,
                        "headers": dict(resp.headers),
                        "url": url,
                    }))]

            if name == "send_batch":
                url = args["url"]
                requests_data = json.loads(args["requests_json"])
                results = []
                async with httpx.AsyncClient(timeout=self._default_timeout) as client:
                    for i, item in enumerate(requests_data):
                        payload = item if isinstance(item, dict) else json.loads(item)
                        resp = await client.post(url, json=payload)
                        results.append({
                            "index": i,
                            "status_code": resp.status_code,
                            "body": resp.text[:5000],
                        })
                return [TextContent(type="text", text=json.dumps({"results": results}))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = WebhookServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool,
                         server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
