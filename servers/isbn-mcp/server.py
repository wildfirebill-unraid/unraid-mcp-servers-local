import sys
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio
import isbnlib

RGG_MAP = {
    "0": "English (UK, US, Australia, NZ, Canada, etc.)",
    "1": "English (UK, US, Australia, NZ, Canada, etc.)",
    "2": "French (France, Belgium, Canada, Switzerland)",
    "3": "German (Germany, Austria, Switzerland)",
    "4": "Japanese",
    "5": "Russian (Russia, former USSR)",
    "6": "Chinese",
    "7": "Chinese",
    "80": "Czech, Slovak",
    "81": "Hindi, Tamil, etc. (India)",
    "82": "Norwegian",
    "83": "Polish",
    "84": "Spanish (Spain)",
    "85": "Portuguese (Brazil)",
    "86": "Serbian, Croatian",
    "87": "Danish",
    "88": "Italian",
    "89": "Korean",
    "90": "Dutch (Netherlands, Belgium)",
    "91": "Swedish",
    "92": "International (UNESCO, EU)",
    "93": "Indonesian",
    "94": "Dutch (Netherlands)",
    "950": "Argentinian",
    "951": "Finnish",
    "952": "Finnish",
    "953": "Croatian",
    "954": "Bulgarian",
    "955": "Sri Lankan",
    "956": "Chilean",
    "957": "Taiwanese",
    "958": "Colombian",
    "959": "Cuban",
    "960": "Greek",
    "961": "Slovenian",
    "962": "Hong Kong",
    "963": "Hungarian",
    "964": "Iranian",
    "965": "Israeli",
    "966": "Ukrainian",
    "967": "Malaysian",
    "968": "Mexican",
    "969": "Pakistani",
    "970": "Mexican",
    "971": "Philippine",
    "972": "Portuguese",
    "973": "Romanian",
    "974": "Thai",
    "975": "Turkish",
    "976": "Caribbean",
    "977": "Egyptian",
    "978": "Nigerian",
    "979": "Indonesian",
    "980": "Venezuelan",
    "981": "Singaporean",
    "982": "South Pacific",
    "983": "Bangladeshi",
    "984": "Belarusian",
    "985": "Taiwanese",
    "986": "Peruvian",
    "987": "Argentinian",
    "988": "Hong Kong",
    "989": "Portuguese",
    "9920": "Ecuadorian",
    "9921": "Philippine",
    "9922": "Bolivian",
    "9923": "Salvadoran",
    "9924": "Cypriot",
    "9925": "Costa Rican",
    "9926": "Jordanian",
    "9927": "Iraqi",
    "9928": "Panamanian",
    "9929": "Dominican",
    "9930": "Icelandic",
    "9931": "Kazakh",
    "9932": "Guatemalan",
    "9933": "Syrian",
    "9934": "Ethiopian",
    "9935": "Kenyan",
    "9936": "Qatari",
    "9937": "Omani",
    "9938": "Tunisian",
    "9939": "Lebanese",
    "9940": "Moroccan",
    "9941": "Algerian",
    "9942": "Icelandic",
    "9943": "Saudi Arabian",
    "9944": "Egyptian",
    "9945": "Indian",
    "9946": "Indonesian",
    "9947": "Pakistani",
    "9948": "Malaysian",
    "9949": "Nigerian",
    "9950": "Bangladeshi",
    "9951": "Albanian",
    "9952": "Uruguayan",
    "9953": "Paraguayan",
    "9954": "Bosnian",
    "9955": "Mongolian",
    "9956": "Myanmar",
    "9957": "Cambodian",
    "9958": "Bahrain",
    "9959": "Maltese",
    "9960": "Saudi Arabian",
    "9961": "Algerian",
    "9962": "Panamanian",
    "9963": "Syrian",
    "9964": "Kazakh",
    "9965": "Kenyan",
    "9966": "Nigerian",
    "9967": "Tunisian",
    "9968": "Omani",
    "9969": "Ethiopian",
    "9970": "Jordanian",
    "9971": "Armenian",
    "9972": "Togolese",
    "9973": "Beninese",
    "9974": "Guinean",
    "9975": "Gabonese",
    "9976": "Ghanaian",
    "9977": "Ugandan",
    "9978": "Mozambican",
    "9979": "Chadian",
    "9980": "Iraqi",
    "9981": "Sudanese",
    "9982": "Malagasy",
    "9983": "Malawian",
    "9984": "Mauritian",
    "9985": "Tajik",
    "9986": "Burkinabe",
    "9987": "Azerbaijani",
    "9988": "Georgian",
    "9989": "Moldovan",
    "99901": "Sudanese",
    "99902": "Namibian",
    "99903": "Mauritian",
    "99904": "Kyrgyz",
    "99905": "Guinean",
    "99906": "Malawian",
    "99907": "Maltese",
    "99908": "Mongolian",
    "99909": "Iraqi",
    "99910": "Kazakh",
    "99911": "Indonesian",
    "99912": "Czech",
    "99913": "Serbian",
    "99914": "Mauritanian",
    "99915": "Turkish",
    "99916": "Sri Lankan",
    "99917": "Filipino",
    "99918": "Iranian",
    "99919": "Nepalese",
    "99920": "Jordanian",
    "99921": "Omani",
    "99922": "Ethiopian",
    "99923": "Polynesian",
    "99924": "Catalan",
    "99925": "Palestinian",
    "99926": "Armenian",
    "99927": "Honduran",
}


class IsbnServer(Server):
    def __init__(self):
        super().__init__("isbn")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="validate", description="Validate an ISBN-10 or ISBN-13 string", inputSchema={"type": "object", "properties": {"isbn": {"type": "string", "description": "ISBN-10 or ISBN-13 to validate"}}, "required": ["isbn"]}),
            Tool(name="convert", description="Convert between ISBN-10 and ISBN-13", inputSchema={"type": "object", "properties": {"isbn": {"type": "string", "description": "ISBN to convert"}}, "required": ["isbn"]}),
            Tool(name="info", description="Get ISBN metadata including registration group, publisher, etc.", inputSchema={"type": "object", "properties": {"isbn": {"type": "string", "description": "ISBN to look up"}}, "required": ["isbn"]}),
            Tool(name="isbn_info", description="Get detailed ISBN structure info (prefix, registration group, check digit)", inputSchema={"type": "object", "properties": {"isbn": {"type": "string", "description": "ISBN to analyze"}}, "required": ["isbn"]}),
            Tool(name="mask", description="Format ISBN with hyphens", inputSchema={"type": "object", "properties": {"isbn": {"type": "string", "description": "ISBN to format"}}, "required": ["isbn"]}),
            Tool(name="classify", description="Classify ISBN by language/region group", inputSchema={"type": "object", "properties": {"isbn": {"type": "string", "description": "ISBN to classify"}}, "required": ["isbn"]}),
            Tool(name="to_isbn13", description="Convert ISBN to ISBN-13 format", inputSchema={"type": "object", "properties": {"isbn": {"type": "string", "description": "ISBN to convert"}}, "required": ["isbn"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "validate":
                isbn = args.get("isbn", "")
                clean = isbnlib.get_isbnlike(isbn, level='normal')
                if not clean:
                    result = {"valid": False, "isbn10": False, "isbn13": False, "normalized": ""}
                else:
                    c = clean[0]
                    v10 = isbnlib.is_isbn10(c)
                    v13 = isbnlib.is_isbn13(c)
                    result = {"valid": v10 or v13, "isbn10": v10, "isbn13": v13, "normalized": c}
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "convert":
                isbn = args.get("isbn", "")
                if isbnlib.is_isbn13(isbn):
                    conv = isbnlib.to_isbn10(isbn)
                    if not conv:
                        raise ValueError("Cannot convert to ISBN-10 (not a valid ISBN-13)")
                    result = {"isbn10": conv, "isbn13": isbn, "from": "isbn13", "to": "isbn10"}
                elif isbnlib.is_isbn10(isbn):
                    conv = isbnlib.to_isbn13(isbn)
                    if not conv:
                        raise ValueError("Cannot convert to ISBN-13 (not a valid ISBN-10)")
                    result = {"isbn13": conv, "isbn10": isbn, "from": "isbn10", "to": "isbn13"}
                else:
                    raise ValueError(f"Not a valid ISBN: {isbn}")
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "info":
                isbn = args.get("isbn", "")
                clean = isbnlib.get_isbnlike(isbn)
                if not clean:
                    raise ValueError(f"Not a valid ISBN: {isbn}")
                clean = clean[0]
                try:
                    meta = isbnlib.meta(clean)
                except Exception:
                    meta = None
                if meta:
                    result = {"isbn": clean, "title": meta.get("Title", ""), "authors": meta.get("Authors", []), "publisher": meta.get("Publisher", ""), "year": meta.get("Year", "")}
                else:
                    local = isbnlib.info(clean)
                    result = {"isbn": clean, "note": "Online metadata unavailable", "local_info": local}
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "isbn_info":
                isbn = args.get("isbn", "")
                clean = isbnlib.get_isbnlike(isbn)
                if not clean:
                    raise ValueError(f"Not a valid ISBN: {isbn}")
                clean = clean[0]
                raw = isbnlib.info(clean)
                result = {"isbn": clean, "prefix": raw.get("Prefix", ""), "registration_group": raw.get("Registration group", ""), "registrant": raw.get("Registrant", ""), "publication": raw.get("Publication", ""), "check_digit": raw.get("Check digit", ""), "length": len(clean.replace("-", ""))}
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "mask":
                isbn = args.get("isbn", "")
                clean = isbnlib.get_isbnlike(isbn)
                if not clean:
                    raise ValueError(f"Not a valid ISBN: {isbn}")
                clean = clean[0]
                masked = isbnlib.mask(clean)
                result = {"original": isbn, "masked": masked}
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "classify":
                isbn = args.get("isbn", "")
                clean = isbnlib.get_isbnlike(isbn)
                if not clean:
                    raise ValueError(f"Not a valid ISBN: {isbn}")
                clean = clean[0]
                local = isbnlib.info(clean)
                rg = local.get("Registration group", "")
                rg_label = RGG_MAP.get(rg, "Unknown registration group")
                result = {"isbn": clean, "registration_group": rg, "region_language": rg_label, "prefix": local.get("Prefix", "")}
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "to_isbn13":
                isbn = args.get("isbn", "")
                if isbnlib.is_isbn13(isbn):
                    result = {"isbn13": isbn, "already_isbn13": True}
                elif isbnlib.is_isbn10(isbn):
                    conv = isbnlib.to_isbn13(isbn)
                    if not conv:
                        raise ValueError("Cannot convert to ISBN-13")
                    result = {"isbn13": conv, "isbn10": isbn, "already_isbn13": False}
                else:
                    raise ValueError(f"Not a valid ISBN: {isbn}")
                return [TextContent(type="text", text=json.dumps(result))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = IsbnServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
