import sys
import json
import os
import math
import ipaddress
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

try:
    import maxminddb
except ImportError:
    maxminddb = None


EARTH_RADIUS_KM = 6371.0


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class GeoIpServer(Server):
    def __init__(self):
        super().__init__("geo-ip")
        self._init_env()
        self._reader: maxminddb.Reader | None = None
        self._asn_reader: maxminddb.Reader | None = None

    def _init_env(self):
        self._geoip_db_path = os.environ.get("GEOIP_DB_PATH", "/data/GeoLite2-City.mmdb")
        self._asn_db_path = os.environ.get("GEOIP_ASN_DB_PATH", "")

    def _get_reader(self) -> maxminddb.Reader:
        if maxminddb is None:
            raise RuntimeError("maxminddb package not installed")
        if self._reader is None:
            p = Path(self._geoip_db_path)
            if not p.exists():
                raise RuntimeError(f"GeoIP database not found at {self._geoip_db_path}. Set GEOIP_DB_PATH env var.")
            self._reader = maxminddb.open_database(str(p), maxminddb.MODE_AUTO)
        return self._reader

    def _get_asn_reader(self) -> maxminddb.Reader | None:
        if maxminddb is None:
            return None
        if self._asn_reader is None and self._asn_db_path:
            p = Path(self._asn_db_path)
            if p.exists():
                self._asn_reader = maxminddb.open_database(str(p), maxminddb.MODE_AUTO)
        return self._asn_reader

    def _ip_to_int(self, ip: str) -> int:
        return int(ipaddress.ip_address(ip))

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="lookup_ip",
                description="Look up an IP address in the GeoLite2 database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ip": {"type": "string", "description": "IPv4 or IPv6 address"}
                    },
                    "required": ["ip"]
                }
            ),
            Tool(
                name="lookup_ips",
                description="Batch lookup multiple IPs (JSON array of strings)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ips_json": {"type": "string", "description": "JSON array of IP strings"}
                    },
                    "required": ["ips_json"]
                }
            ),
            Tool(
                name="city_info",
                description="Get city-level geolocation for an IP",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ip": {"type": "string", "description": "IPv4 or IPv6 address"}
                    },
                    "required": ["ip"]
                }
            ),
            Tool(
                name="country_info",
                description="Get country-level geolocation for an IP",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ip": {"type": "string", "description": "IPv4 or IPv6 address"}
                    },
                    "required": ["ip"]
                }
            ),
            Tool(
                name="asn_info",
                description="Get ASN information for an IP (if GeoLite2-ASN database is available)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ip": {"type": "string", "description": "IPv4 or IPv6 address"}
                    },
                    "required": ["ip"]
                }
            ),
            Tool(
                name="db_info",
                description="Get metadata about the loaded GeoIP database",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="search_nearby",
                description="Search IPs near coordinates (not supported with GeoLite2 database)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lat": {"type": "number", "description": "Latitude"},
                        "lon": {"type": "number", "description": "Longitude"},
                        "radius_km": {"type": "number", "description": "Radius in kilometers"}
                    },
                    "required": ["lat", "lon", "radius_km"]
                }
            ),
            Tool(
                name="distance_between",
                description="Calculate approximate distance between two IPs in kilometers",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ip1": {"type": "string", "description": "First IP"},
                        "ip2": {"type": "string", "description": "Second IP"}
                    },
                    "required": ["ip1", "ip2"]
                }
            ),
        ]

    def _lookup(self, ip: str) -> dict[str, Any]:
        reader = self._get_reader()
        try:
            result = reader.get(ip)
        except Exception as e:
            raise RuntimeError(f"lookup failed for {ip}: {e}")
        if result is None:
            raise RuntimeError(f"no data found for IP: {ip}")
        return result

    def _extract_city(self, ip: str) -> dict[str, Any]:
        data = self._lookup(ip)
        loc = data.get("location", {})
        city = data.get("city", {})
        sub = data.get("subdivisions", [{}])[0] if data.get("subdivisions") else {}
        country = data.get("country", {})
        return {
            "ip": ip,
            "city": city.get("names", {}).get("en"),
            "subdivision": sub.get("names", {}).get("en"),
            "country": country.get("names", {}).get("en"),
            "country_code": country.get("iso_code"),
            "continent": data.get("continent", {}).get("names", {}).get("en"),
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"),
            "accuracy_radius": loc.get("accuracy_radius"),
            "timezone": loc.get("time_zone"),
            "postal_code": data.get("postal", {}).get("code"),
        }

    def _extract_country(self, ip: str) -> dict[str, Any]:
        data = self._lookup(ip)
        country = data.get("country", {})
        continent = data.get("continent", {})
        registered = data.get("registered_country", {})
        return {
            "ip": ip,
            "country": country.get("names", {}).get("en"),
            "country_code": country.get("iso_code"),
            "continent": continent.get("names", {}).get("en"),
            "continent_code": continent.get("code"),
            "registered_country": registered.get("names", {}).get("en"),
            "registered_country_code": registered.get("iso_code"),
        }

    def _extract_asn(self, ip: str) -> dict[str, Any]:
        reader = self._get_asn_reader()
        if reader is None:
            p = Path(self._asn_db_path) if self._asn_db_path else Path(self._geoip_db_path).parent / "GeoLite2-ASN.mmdb"
            if p.exists():
                self._asn_reader = maxminddb.open_database(str(p), maxminddb.MODE_AUTO)
                reader = self._asn_reader
        if reader is None:
            raise RuntimeError("ASN database not available. Set GEOIP_ASN_DB_PATH or place GeoLite2-ASN.mmdb alongside the city DB.")
        try:
            data = reader.get(ip)
        except Exception as e:
            raise RuntimeError(f"ASN lookup failed for {ip}: {e}")
        if data is None:
            raise RuntimeError(f"no ASN data found for IP: {ip}")
        return {
            "ip": ip,
            "asn": data.get("autonomous_system_number"),
            "org": data.get("autonomous_system_organization"),
        }

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "lookup_ip":
                ip = args["ip"]
                data = self._lookup(ip)
                return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]

            elif name == "lookup_ips":
                ips = json.loads(args["ips_json"])
                results = []
                for ip in ips:
                    try:
                        results.append({"ip": ip, "data": self._lookup(ip)})
                    except RuntimeError as e:
                        results.append({"ip": ip, "error": str(e)})
                return [TextContent(type="text", text=json.dumps(results, indent=2, default=str))]

            elif name == "city_info":
                ip = args["ip"]
                data = self._extract_city(ip)
                return [TextContent(type="text", text=json.dumps(data, indent=2))]

            elif name == "country_info":
                ip = args["ip"]
                data = self._extract_country(ip)
                return [TextContent(type="text", text=json.dumps(data, indent=2))]

            elif name == "asn_info":
                ip = args["ip"]
                data = self._extract_asn(ip)
                return [TextContent(type="text", text=json.dumps(data, indent=2))]

            elif name == "db_info":
                reader = self._get_reader()
                metadata = reader.metadata()
                return [TextContent(type="text", text=json.dumps({
                    "database_type": metadata.database_type,
                    "binary_format_major_version": metadata.binary_format_major_version,
                    "binary_format_minor_version": metadata.binary_format_minor_version,
                    "build_epoch": metadata.build_epoch,
                    "description": metadata.description,
                    "ip_version": metadata.ip_version,
                    "languages": metadata.languages,
                    "node_count": metadata.node_count,
                    "record_size": metadata.record_size,
                }, indent=2, default=str))]

            elif name == "search_nearby":
                return [TextContent(type="text", text=json.dumps({
                    "error": "search_nearby is not supported with GeoLite2 databases. GeoLite2 does not support coordinate-based reverse lookups."
                }, indent=2))]

            elif name == "distance_between":
                ip1 = args["ip1"]
                ip2 = args["ip2"]
                loc1 = self._extract_city(ip1)
                loc2 = self._extract_city(ip2)
                if loc1.get("latitude") is None or loc1.get("longitude") is None:
                    return [TextContent(type="text", text=json.dumps({"error": f"no location data for {ip1}"}, indent=2))]
                if loc2.get("latitude") is None or loc2.get("longitude") is None:
                    return [TextContent(type="text", text=json.dumps({"error": f"no location data for {ip2}"}, indent=2))]
                dist = _haversine(loc1["latitude"], loc1["longitude"], loc2["latitude"], loc2["longitude"])
                return [TextContent(type="text", text=json.dumps({
                    "ip1": ip1, "loc1": {"lat": loc1["latitude"], "lon": loc1["longitude"]},
                    "ip2": ip2, "loc2": {"lat": loc2["latitude"], "lon": loc2["longitude"]},
                    "distance_km": round(dist, 2),
                }, indent=2))]

            raise ValueError(f"Unknown tool: {name}")
        except RuntimeError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = GeoIpServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
