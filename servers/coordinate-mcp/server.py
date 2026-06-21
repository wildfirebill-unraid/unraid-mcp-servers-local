import json
import re
import math

from geopy.distance import distance as geopy_distance, geodesic
from geopy.point import Point

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

UNIT_MAP = {
    "km": "kilometers",
    "mi": "miles",
    "nm": "nautical_miles",
    "m": "meters",
    "ft": "feet",
}


def _distance_in_unit(point1, point2, unit: str) -> float:
    d = geopy_distance(point1, point2)
    unit_key = UNIT_MAP.get(unit, unit)
    if unit_key == "kilometers":
        return d.kilometers
    elif unit_key == "miles":
        return d.miles
    elif unit_key == "nautical_miles":
        return d.nautical
    elif unit_key == "meters":
        return d.meters
    elif unit_key == "feet":
        return d.feet
    else:
        return d.kilometers


def _parse_coordinate_string(coord_str: str) -> tuple[float, float]:
    coord_str = coord_str.strip().replace("\u00b0", " ").replace("\u2032", " ").replace("\u2033", " ")
    dms_pattern = re.compile(
        r"(-?\d+(?:\.\d+)?)\s*(?:deg|°|\s)?\s*"
        r"(?:(\d+(?:\.\d+)?)\s*(?:['\u2032]|\s)?\s*)?"
        r"(?:(\d+(?:\.\d+)?)\s*(?:\"|\u2033)?)?\s*"
        r"([NSEW])?"
    )
    coord_str_clean = coord_str.replace(",", " ")
    parts = coord_str_clean.split()
    if len(parts) >= 2:
        try:
            lat = float(parts[0].rstrip("NSEW"))
            if "S" in parts[0] or "S" == parts[-1]:
                pass
            lon = float(parts[1].rstrip("NSEW"))
            if len(parts) >= 2:
                for char in parts[0]:
                    if char == "S":
                        lat = -abs(lat)
                    elif char == "N":
                        lat = abs(lat)
                for char in parts[1]:
                    if char == "W":
                        lon = -abs(lon)
                    elif char == "E":
                        lon = abs(lon)
            point = Point(lat, lon)
            return point.latitude, point.longitude
        except ValueError:
            pass
    try:
        point = Point(coord_str)
        return point.latitude, point.longitude
    except Exception:
        raise ValueError(f"Could not parse coordinate string: '{coord_str}'")


def _dms_to_decimal(degrees, minutes=0, seconds=0, direction=None):
    decimal = abs(float(degrees)) + float(minutes) / 60 + float(seconds) / 3600
    if direction in ("S", "W") or (isinstance(degrees, str) and degrees.startswith("-")):
        decimal = -decimal
    elif isinstance(degrees, (int, float)) and degrees < 0:
        decimal = -decimal
    return decimal


class CoordinateServer(Server):
    def __init__(self):
        super().__init__("coordinate")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="distance", description="Distance between two points in specified unit",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "lat1": {"type": "number", "description": "Latitude of point 1"},
                         "lon1": {"type": "number", "description": "Longitude of point 1"},
                         "lat2": {"type": "number", "description": "Latitude of point 2"},
                         "lon2": {"type": "number", "description": "Longitude of point 2"},
                         "unit": {"type": "string", "description": "Unit: km, mi, nm, m, ft (default km)", "default": "km"}
                     },
                     "required": ["lat1", "lon1", "lat2", "lon2"]
                 }),
            Tool(name="bearing", description="Initial bearing from point 1 to point 2 (degrees)",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "lat1": {"type": "number", "description": "Latitude of point 1"},
                         "lon1": {"type": "number", "description": "Longitude of point 1"},
                         "lat2": {"type": "number", "description": "Latitude of point 2"},
                         "lon2": {"type": "number", "description": "Longitude of point 2"}
                     },
                     "required": ["lat1", "lon1", "lat2", "lon2"]
                 }),
            Tool(name="midpoint", description="Midpoint between two points",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "lat1": {"type": "number", "description": "Latitude of point 1"},
                         "lon1": {"type": "number", "description": "Longitude of point 1"},
                         "lat2": {"type": "number", "description": "Latitude of point 2"},
                         "lon2": {"type": "number", "description": "Longitude of point 2"}
                     },
                     "required": ["lat1", "lon1", "lat2", "lon2"]
                 }),
            Tool(name="destination", description="Calculate destination point from start + bearing + distance",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "lat": {"type": "number", "description": "Starting latitude"},
                         "lon": {"type": "number", "description": "Starting longitude"},
                         "bearing": {"type": "number", "description": "Bearing in degrees (0-360)"},
                         "distance": {"type": "number", "description": "Distance to travel"},
                         "unit": {"type": "string", "description": "Unit: km, mi, nm, m (default km)", "default": "km"}
                     },
                     "required": ["lat", "lon", "bearing", "distance"]
                 }),
            Tool(name="area_polygon", description="Area of a polygon defined by coordinate vertices",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "coordinates_json": {"type": "string", "description": "JSON array of [lat, lon] pairs e.g. '[[0,0],[0,1],[1,1],[1,0]]'"},
                         "unit": {"type": "string", "description": "Output area unit: sq_km, sq_mi (default sq_km)", "default": "sq_km"}
                     },
                     "required": ["coordinates_json"]
                 }),
            Tool(name="format_coords", description="Format coordinates in DMS, decimal, or other format",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "lat": {"type": "number", "description": "Latitude"},
                         "lon": {"type": "number", "description": "Longitude"},
                         "format": {"type": "string", "description": "Format: 'dms' (deg min sec), 'decimal' (default), 'dms_compact' (no symbols)"}
                     },
                     "required": ["lat", "lon"]
                 }),
            Tool(name="parse_coords", description="Parse a coordinate string into decimal lat/lon",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "coords_str": {"type": "string", "description": "Coordinate string e.g. '40.7128° N, 74.0060° W' or '51°30\\u2032N 0°07\\u2032W'"}
                     },
                     "required": ["coords_str"]
                 }),
            Tool(name="is_within_radius", description="Check if a point falls within a radius of a center point",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "center_lat": {"type": "number", "description": "Center latitude"},
                         "center_lon": {"type": "number", "description": "Center longitude"},
                         "point_lat": {"type": "number", "description": "Point latitude to check"},
                         "point_lon": {"type": "number", "description": "Point longitude to check"},
                         "radius": {"type": "number", "description": "Radius distance"},
                         "unit": {"type": "string", "description": "Unit: km, mi, nm, m (default km)", "default": "km"}
                     },
                     "required": ["center_lat", "center_lon", "point_lat", "point_lon", "radius"]
                 }),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "distance":
                p1 = Point(args["lat1"], args["lon1"])
                p2 = Point(args["lat2"], args["lon2"])
                unit = args.get("unit", "km")
                d = _distance_in_unit(p1, p2, unit)
                return [TextContent(type="text", text=json.dumps({
                    "from": {"lat": args["lat1"], "lon": args["lon1"]},
                    "to": {"lat": args["lat2"], "lon": args["lon2"]},
                    "distance": d,
                    "unit": unit
                }))]

            elif name == "bearing":
                p1 = Point(args["lat1"], args["lon1"])
                p2 = Point(args["lat2"], args["lon2"])
                d = geopy_distance(p1, p2)
                bearing = d.initial
                return [TextContent(type="text", text=json.dumps({
                    "from": {"lat": args["lat1"], "lon": args["lon1"]},
                    "to": {"lat": args["lat2"], "lon": args["lon2"]},
                    "initial_bearing": bearing
                }))]

            elif name == "midpoint":
                p1 = Point(args["lat1"], args["lon1"])
                p2 = Point(args["lat2"], args["lon2"])
                lat1_r = math.radians(p1.latitude)
                lon1_r = math.radians(p1.longitude)
                lat2_r = math.radians(p2.latitude)
                lon2_r = math.radians(p2.longitude)
                d = geopy_distance(p1, p2)
                bearing = math.radians(d.initial)
                dist = _distance_in_unit(p1, p2, "km") * 1000
                d_angle = dist / 6371000.0
                bx = math.cos(lat2_r) * math.cos(lon2_r - lon1_r)
                by = math.cos(lat2_r) * math.sin(lon2_r - lon1_r)
                lat3 = math.atan2(
                    math.sin(lat1_r) + math.sin(lat2_r),
                    math.sqrt((math.cos(lat1_r) + bx) ** 2 + by ** 2)
                )
                lon3 = lon1_r + math.atan2(by, math.cos(lat1_r) + bx)
                mid_lat = math.degrees(lat3)
                mid_lon = math.degrees(lon3)
                return [TextContent(type="text", text=json.dumps({
                    "from": {"lat": args["lat1"], "lon": args["lon1"]},
                    "to": {"lat": args["lat2"], "lon": args["lon2"]},
                    "midpoint": {"lat": round(mid_lat, 6), "lon": round(mid_lon, 6)}
                }))]

            elif name == "destination":
                start = Point(args["lat"], args["lon"])
                bearing = float(args["bearing"])
                dist = float(args["distance"])
                unit = args.get("unit", "km")
                unit_key = UNIT_MAP.get(unit, unit)
                if unit_key == "kilometers":
                    d = dist
                elif unit_key == "miles":
                    d = dist * 1.609344
                elif unit_key == "nautical_miles":
                    d = dist * 1.852
                elif unit_key == "meters":
                    d = dist / 1000.0
                else:
                    d = dist
                dest = geodesic(kilometers=d).destination(start, bearing)
                return [TextContent(type="text", text=json.dumps({
                    "start": {"lat": args["lat"], "lon": args["lon"]},
                    "bearing": bearing,
                    "distance": dist,
                    "unit": unit,
                    "destination": {"lat": round(dest.latitude, 6), "lon": round(dest.longitude, 6)}
                }))]

            elif name == "area_polygon":
                coords = json.loads(args["coordinates_json"])
                if len(coords) < 3:
                    raise ValueError("Polygon must have at least 3 vertices")
                points = [Point(lat, lon) for lat, lon in coords]
                area_sqm = _polygon_area_sqm(points)
                unit = args.get("unit", "sq_km")
                if unit == "sq_km":
                    area = area_sqm / 1e6
                elif unit == "sq_mi":
                    area = area_sqm / 2.589988e6
                else:
                    area = area_sqm
                return [TextContent(type="text", text=json.dumps({
                    "vertices": len(coords),
                    "area": round(area, 6),
                    "unit": unit
                }))]

            elif name == "format_coords":
                lat = float(args["lat"])
                lon = float(args["lon"])
                fmt = args.get("format", "decimal")
                if fmt == "decimal":
                    result = {"lat": lat, "lon": lon, "formatted": f"{lat:.6f}, {lon:.6f}"}
                elif fmt == "dms":
                    lat_d = _to_dms(lat, "lat")
                    lon_d = _to_dms(lon, "lon")
                    result = {
                        "lat": lat_d,
                        "lon": lon_d,
                        "formatted": f"{lat_d['d']}°{lat_d['m']}'{lat_d['s']:.1f}\"{lat_d['dir']}  {lon_d['d']}°{lon_d['m']}'{lon_d['s']:.1f}\"{lon_d['dir']}"
                    }
                elif fmt == "dms_compact":
                    lat_d = _to_dms(lat, "lat")
                    lon_d = _to_dms(lon, "lon")
                    result = {
                        "lat": lat_d,
                        "lon": lon_d,
                        "formatted": f"{lat_d['d']} {lat_d['m']} {lat_d['s']:.1f} {lat_d['dir']}  {lon_d['d']} {lon_d['m']} {lon_d['s']:.1f} {lon_d['dir']}"
                    }
                else:
                    raise ValueError(f"Unknown format: {fmt}")
                return [TextContent(type="text", text=json.dumps(result))]

            elif name == "parse_coords":
                lat, lon = _parse_coordinate_string(args["coords_str"])
                return [TextContent(type="text", text=json.dumps({
                    "input": args["coords_str"],
                    "lat": lat,
                    "lon": lon,
                    "formatted": f"{lat:.6f}, {lon:.6f}"
                }))]

            elif name == "is_within_radius":
                center = Point(args["center_lat"], args["center_lon"])
                point = Point(args["point_lat"], args["point_lon"])
                radius = float(args["radius"])
                unit = args.get("unit", "km")
                d = _distance_in_unit(center, point, unit)
                return [TextContent(type="text", text=json.dumps({
                    "center": {"lat": args["center_lat"], "lon": args["center_lon"]},
                    "point": {"lat": args["point_lat"], "lon": args["point_lon"]},
                    "radius": radius,
                    "unit": unit,
                    "distance": d,
                    "is_within": d <= radius
                }))]

            else:
                raise ValueError(f"Unknown tool: {name}")

        except json.JSONDecodeError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Invalid JSON: {str(e)}"}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


def _to_dms(value: float, coord_type: str) -> dict:
    if coord_type == "lat":
        direction = "N" if value >= 0 else "S"
    else:
        direction = "E" if value >= 0 else "W"
    value = abs(value)
    d = int(value)
    m = int((value - d) * 60)
    s = (value - d - m / 60) * 3600
    return {"d": d, "m": m, "s": round(s, 1), "dir": direction}


def _polygon_area_sqm(points: list[Point]) -> float:
    if len(points) < 3:
        return 0.0
    n = len(points)
    area = 0.0
    for i in range(n):
        p1 = points[i]
        p2 = points[(i + 1) % n]
        lat1_r = math.radians(p1.latitude)
        lat2_r = math.radians(p2.latitude)
        lon1_r = math.radians(p1.longitude)
        lon2_r = math.radians(p2.longitude)
        area += math.sin(lat2_r) - math.sin(lat1_r) * (lon2_r - lon1_r)
    area = abs(area) * 6371000.0 ** 2 / 2.0
    return area


async def main():
    server = CoordinateServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
