import os
import json
from pathlib import Path
from datetime import datetime, timezone
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, Resource
import mcp.server.stdio
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import socket
import ssl

BASE = Path(os.environ.get("SSL_BASE_PATH", "/data"))
server = Server("ssl-mcp")

def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else BASE / path

def _cert_to_dict(cert: x509.Certificate) -> dict:
    def _name(n):
        return {attr.oid._name: attr.value for attr in n}
    return {
        "subject": _name(cert.subject),
        "issuer": _name(cert.issuer),
        "serial_number": str(cert.serial_number),
        "not_valid_before": cert.not_valid_before_utc.isoformat(),
        "not_valid_after": cert.not_valid_after_utc.isoformat(),
        "signature_algorithm": cert.signature_algorithm_oid._name,
        "public_key": cert.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode(),
    }

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="cert_info", description="Parse and display SSL certificate from a PEM file", inputSchema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}),
        Tool(name="cert_expiry", description="Check certificate expiry for a host", inputSchema={"type": "object", "properties": {"host": {"type": "string"}, "port": {"type": "integer", "default": 443}, "timeout": {"type": "integer", "default": 10}}, "required": ["host"]}),
        Tool(name="cert_chain", description="Get full certificate chain for a host", inputSchema={"type": "object", "properties": {"host": {"type": "string"}, "port": {"type": "integer", "default": 443}}, "required": ["host"]}),
        Tool(name="generate_csr", description="Generate a CSR", inputSchema={"type": "object", "properties": {"common_name": {"type": "string"}, "country": {"type": "string"}, "state": {"type": "string"}, "locality": {"type": "string"}, "org": {"type": "string"}, "key_size": {"type": "integer", "default": 2048}, "output_dir": {"type": "string"}}, "required": ["common_name", "output_dir"]}),
        Tool(name="generate_self_signed", description="Generate a self-signed cert", inputSchema={"type": "object", "properties": {"common_name": {"type": "string"}, "days_valid": {"type": "integer", "default": 365}, "output_dir": {"type": "string"}, "key_size": {"type": "integer", "default": 2048}}, "required": ["common_name", "output_dir"]}),
    ]

@server.list_resources()
async def list_resources() -> list[Resource]:
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "cert_info":
        path = _resolve(arguments["path"])
        with open(path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        return [TextContent(type="text", text=json.dumps(_cert_to_dict(cert), indent=2))]
    elif name == "cert_expiry":
        host = arguments["host"]
        port = arguments.get("port", 443)
        timeout = arguments.get("timeout", 10)
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                der = ssock.getpeercert(binary_form=True)
        cert = x509.load_der_x509_certificate(der)
        now = datetime.now(timezone.utc)
        expires = cert.not_valid_after_utc
        remaining = (expires - now).days
        return [TextContent(type="text", text=json.dumps({
            "subject": str(cert.subject),
            "issuer": str(cert.issuer),
            "not_valid_after": expires.isoformat(),
            "days_remaining": remaining,
            "expired": now > expires,
        }, indent=2))]
    elif name == "cert_chain":
        host = arguments["host"]
        port = arguments.get("port", 443)
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                chain = ssock.get_verified_chain() or ssock.get_unverified_chain()
        result = []
        for c in chain:
            cert = x509.load_der_x509_certificate(c)
            result.append(_cert_to_dict(cert))
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "generate_csr":
        out = Path(arguments["output_dir"])
        if not out.is_absolute():
            out = BASE / out
        out.mkdir(parents=True, exist_ok=True)
        key_size = arguments.get("key_size", 2048)
        key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
        builder = x509.CertificateSigningRequestBuilder()
        name_attrs = [x509.NameAttribute(NameOID.COMMON_NAME, arguments["common_name"])]
        if arguments.get("country"):
            name_attrs.append(x509.NameAttribute(NameOID.COUNTRY_NAME, arguments["country"]))
        if arguments.get("state"):
            name_attrs.append(x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, arguments["state"]))
        if arguments.get("locality"):
            name_attrs.append(x509.NameAttribute(NameOID.LOCALITY_NAME, arguments["locality"]))
        if arguments.get("org"):
            name_attrs.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, arguments["org"]))
        builder = builder.subject_name(x509.Name(name_attrs))
        csr = builder.sign(key, hashes.SHA256())
        key_path = out / f"{arguments['common_name']}.key"
        csr_path = out / f"{arguments['common_name']}.csr"
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.TraditionalOpenSSL, encryption_algorithm=serialization.NoEncryption()))
        with open(csr_path, "wb") as f:
            f.write(csr.public_bytes(serialization.Encoding.PEM))
        return [TextContent(type="text", text=json.dumps({"key": str(key_path), "csr": str(csr_path)}))]
    elif name == "generate_self_signed":
        out = Path(arguments["output_dir"])
        if not out.is_absolute():
            out = BASE / out
        out.mkdir(parents=True, exist_ok=True)
        key_size = arguments.get("key_size", 2048)
        days = arguments.get("days_valid", 365)
        key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, arguments["common_name"])])
        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now.replace(day=now.day + days))
            .sign(key, hashes.SHA256())
        )
        key_path = out / f"{arguments['common_name']}.key"
        cert_path = out / f"{arguments['common_name']}.crt"
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.TraditionalOpenSSL, encryption_algorithm=serialization.NoEncryption()))
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        return [TextContent(type="text", text=json.dumps({"key": str(key_path), "cert": str(cert_path)}))]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            InitializationOptions(server_name="ssl-mcp", server_version="1.0.0"),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
