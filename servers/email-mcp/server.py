import sys
import json
import os
import re
import email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio


EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class EmailServer(Server):
    def __init__(self):
        super().__init__("email")
        self._init_env()

    def _init_env(self):
        self._smtp_host = os.environ.get("SMTP_HOST", "localhost")
        self._smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self._smtp_user = os.environ.get("SMTP_USER", "")
        self._smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self._smtp_use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
        self._smtp_from = os.environ.get("SMTP_FROM", "")
        self._email_path = os.environ.get("EMAIL_PATH", "")

    def _build_message(self, to: list[str], subject: str, body: str = "",
                       html: str = "", cc: list[str] | None = None,
                       bcc: list[str] | None = None) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._smtp_from
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        if body:
            msg.attach(MIMEText(body, "plain"))
        if html:
            msg.attach(MIMEText(html, "html"))
        return msg

    def _all_recipients(self, to: list[str], cc: list[str] | None,
                        bcc: list[str] | None) -> list[str]:
        result = list(to)
        if cc:
            result.extend(cc)
        if bcc:
            result.extend(bcc)
        return result

    async def _send(self, msg: MIMEMultipart, recipients: list[str]):
        import aiosmtplib
        use_tls = self._smtp_use_tls and self._smtp_port != 465
        use_ssl = self._smtp_port == 465
        await aiosmtplib.send(
            msg,
            hostname=self._smtp_host,
            port=self._smtp_port,
            username=self._smtp_user or None,
            password=self._smtp_password or None,
            use_tls=use_tls,
            use_ssl=use_ssl,
            recipients=recipients,
        )

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="send_email", description="Send a plain text email",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "to": {"type": "array", "items": {"type": "string"}, "description": "List of recipient email addresses"},
                         "subject": {"type": "string"},
                         "body": {"type": "string"},
                         "cc": {"type": "array", "items": {"type": "string"}},
                         "bcc": {"type": "array", "items": {"type": "string"}},
                         "html": {"type": "string"},
                     },
                     "required": ["to", "subject"],
                 }),
            Tool(name="send_html_email", description="Send an HTML email",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "to": {"type": "array", "items": {"type": "string"}, "description": "List of recipient email addresses"},
                         "subject": {"type": "string"},
                         "html": {"type": "string"},
                         "cc": {"type": "array", "items": {"type": "string"}},
                         "bcc": {"type": "array", "items": {"type": "string"}},
                     },
                     "required": ["to", "subject", "html"],
                 }),
            Tool(name="send_with_attachment", description="Send email with file attachments",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "to": {"type": "array", "items": {"type": "string"}, "description": "List of recipient email addresses"},
                         "subject": {"type": "string"},
                         "body": {"type": "string"},
                         "attachment_paths": {"type": "array", "items": {"type": "string"}, "description": "List of file paths to attach"},
                         "cc": {"type": "array", "items": {"type": "string"}},
                         "bcc": {"type": "array", "items": {"type": "string"}},
                     },
                     "required": ["to", "subject", "attachment_paths"],
                 }),
            Tool(name="validate_email", description="Validate an email address format",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "address": {"type": "string"},
                     },
                     "required": ["address"],
                 }),
            Tool(name="parse_email", description="Parse a raw email string into components",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "raw": {"type": "string"},
                     },
                     "required": ["raw"],
                 }),
            Tool(name="preview_email", description="Preview what would be sent (dry run, no send)",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "to": {"type": "array", "items": {"type": "string"}, "description": "List of recipient email addresses"},
                         "subject": {"type": "string"},
                         "body": {"type": "string"},
                     },
                     "required": ["to", "subject"],
                 }),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "send_email":
                to = args["to"]
                msg = self._build_message(
                    to=to, subject=args["subject"], body=args.get("body", ""),
                    html=args.get("html", ""), cc=args.get("cc"), bcc=args.get("bcc"))
                recipients = self._all_recipients(to, args.get("cc"), args.get("bcc"))
                await self._send(msg, recipients)
                return [TextContent(type="text", text=json.dumps({"status": "sent", "to": to, "subject": args["subject"]}))]

            if name == "send_html_email":
                to = args["to"]
                msg = self._build_message(
                    to=to, subject=args["subject"], html=args["html"],
                    cc=args.get("cc"), bcc=args.get("bcc"))
                recipients = self._all_recipients(to, args.get("cc"), args.get("bcc"))
                await self._send(msg, recipients)
                return [TextContent(type="text", text=json.dumps({"status": "sent", "to": to, "subject": args["subject"]}))]

            if name == "send_with_attachment":
                to = args["to"]
                msg = MIMEMultipart()
                msg["Subject"] = args["subject"]
                msg["From"] = self._smtp_from
                msg["To"] = ", ".join(to)
                if args.get("cc"):
                    msg["Cc"] = ", ".join(args["cc"])
                if args.get("body"):
                    msg.attach(MIMEText(args["body"], "plain"))
                base_path = Path(self._email_path) if self._email_path else Path()
                for apath in args["attachment_paths"]:
                    fpath = Path(apath)
                    if not fpath.is_absolute():
                        fpath = base_path / fpath
                    if not fpath.exists():
                        raise FileNotFoundError(f"Attachment not found: {fpath}")
                    with open(fpath, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={fpath.name}")
                    msg.attach(part)
                recipients = self._all_recipients(to, args.get("cc"), args.get("bcc"))
                await self._send(msg, recipients)
                return [TextContent(type="text", text=json.dumps({"status": "sent", "to": to, "subject": args["subject"]}))]

            if name == "validate_email":
                valid = bool(EMAIL_RE.match(args["address"]))
                return [TextContent(type="text", text=json.dumps({"valid": valid, "address": args["address"]}))]

            if name == "parse_email":
                parsed = email.message_from_string(args["raw"])
                result = {
                    "from": parsed.get("From", ""),
                    "to": parsed.get("To", ""),
                    "cc": parsed.get("Cc", ""),
                    "subject": parsed.get("Subject", ""),
                    "body": "",
                }
                if parsed.is_multipart():
                    for part in parsed.walk():
                        if part.get_content_type() == "text/plain":
                            result["body"] = part.get_payload(decode=True).decode("utf-8", errors="replace")
                            break
                else:
                    result["body"] = parsed.get_payload(decode=True).decode("utf-8", errors="replace")
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "preview_email":
                msg = self._build_message(to=args["to"], subject=args["subject"], body=args.get("body", ""))
                preview = {
                    "from": self._smtp_from,
                    "to": args["to"],
                    "subject": args["subject"],
                    "body_preview": args.get("body", "")[:500],
                    "body_length": len(args.get("body", "")),
                    "smtp_host": self._smtp_host,
                    "smtp_port": self._smtp_port,
                    "use_tls": self._smtp_use_tls,
                }
                return [TextContent(type="text", text=json.dumps(preview))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = EmailServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool,
                         server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
