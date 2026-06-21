#!/usr/bin/env python3
"""Generate 69 MCP servers with stub implementations, Dockerfiles, and requirements."""

import os
import json

SERVERS_DIR = r"G:\zed\unraid_mcp_servers\servers"

servers = [
    # (name, description, tools_list, pip_deps, apt_deps, env_vars)
    # === DATABASE (7) ===
    ("postgresql-mcp", "PostgreSQL database querying and schema inspection via psycopg2",
     "list_databases,list_tables,describe_table,execute_query,get_server_info",
     "psycopg2-binary", "", "PGHOST,PGPORT,PGUSER,PGPASSWORD,PGDATABASE"),
    ("mysql-mcp", "MySQL/MariaDB database operations via PyMySQL",
     "list_databases,list_tables,describe_table,execute_query,server_status",
     "pymysql", "", "MYSQL_HOST,MYSQL_PORT,MYSQL_USER,MYSQL_PASSWORD,MYSQL_DATABASE"),
    ("redis-mcp", "Redis key-value operations: get, set, delete, keys, server info via redis-py",
     "get_key,set_key,delete_key,list_keys,get_info,ping_server,get_key_ttl,increment_key",
     "redis", "", "REDIS_HOST,REDIS_PORT,REDIS_PASSWORD,REDIS_DB"),
    ("mongodb-mcp", "MongoDB document database operations via PyMongo",
     "list_databases,list_collections,find_documents,insert_document,update_document,delete_document,aggregate,collection_stats",
     "pymongo", "", "MONGODB_URI,MONGODB_DATABASE"),
    ("elasticsearch-mcp", "Elasticsearch cluster operations via elasticsearch-py",
     "cluster_health,list_indices,search,get_document,index_document,delete_index,get_mapping,get_index_stats",
     "elasticsearch", "", "ES_HOST,ES_PORT"),
    ("influxdb-mcp", "InfluxDB time series operations via influxdb-client",
     "list_buckets,write_point,query_flux,list_measurements,delete_data,get_health",
     "influxdb-client", "", "INFLUXDB_URL,INFLUXDB_TOKEN,INFLUXDB_ORG"),
    ("memcached-mcp", "Memcached operations via pymemcache",
     "get_value,set_value,delete_key,flush_all,server_stats,get_multi,set_multi",
     "pymemcache", "", "MEMCACHED_HOST,MEMCACHED_PORT"),

    # === NETWORK & SECURITY (9) ===
    ("port-scanner-mcp", "TCP port scanning with connect scan, service detection, banner grabbing",
     "scan_ports,quick_scan,scan_common_ports,service_detect,banner_grab",
     "", "", ""),
    ("dns-resolver-mcp", "DNS record lookups: A, AAAA, MX, TXT, NS, CNAME, SOA, SRV via dnspython",
     "resolve_a,resolve_aaaa,resolve_mx,resolve_txt,resolve_ns,resolve_cname,resolve_soa,resolve_srv,reverse_lookup",
     "dnspython", "", ""),
    ("traceroute-mcp", "Network path tracing with per-hop timing and path analysis",
     "traceroute,trace_quick,path_analysis,hop_details",
     "", "inetutils-traceroute", ""),
    ("net-connections-mcp", "Active network connections, listening sockets, interface stats via psutil",
     "list_connections,list_listeners,interface_stats,connection_summary,bandwidth_usage",
     "psutil", "", ""),
    ("fail2ban-mcp", "Fail2ban jail management: status, ban/unban IPs, log tail",
     "jail_status,list_jails,ban_ip,unban_ip,jail_log,banned_ips",
     "", "", ""),
    ("wireguard-mcp", "WireGuard VPN interface management: peer status, handshake times, config",
     "list_interfaces,peer_status,show_config,interface_stats,list_peers,handshake_info",
     "", "wireguard-tools", ""),
    ("nmap-lite-mcp", "Python-based network discovery: ping sweep, port scan, service enumeration",
     "ping_sweep,port_scan,service_enum,subnet_scan,quick_discovery",
     "", "", ""),
    ("geo-ip-mcp", "IP geolocation using local MaxMind GeoLite2 database via geoip2",
     "geoip_lookup,geoip_city,geoip_asn,geoip_country",
     "geoip2", "", "GEOIP_DB_PATH"),
    ("firewall-mcp", "Linux iptables/nftables firewall: list rules, chains, policy info",
     "list_rules,list_chains,rule_count,policy_info,list_nat,search_rules",
     "", "iptables", ""),

    # === SYSTEM MANAGEMENT (9) ===
    ("journald-mcp", "Systemd journal reader: query logs by unit, priority, time range, boot",
     "query_logs,journal_boot,journal_priority,journal_unit,journal_since,journal_fields",
     "", "", ""),
    ("users-groups-mcp", "User and group management: list, info, group members, login history",
     "list_users,list_groups,user_info,group_members,login_history,last_logins",
     "", "", ""),
    ("packages-mcp", "Package management: list installed, search, info, dependency tree via dpkg/rpm",
     "list_installed,search_packages,package_info,package_files,package_deps,check_update",
     "", "", ""),
    ("kernel-mcp", "Kernel parameters (sysctl) and module management",
     "list_modules,module_info,sysctl_get,sysctl_list,kernel_info,module_parameters",
     "", "", ""),
    ("nfs-mcp", "NFS server export management: exports, clients, status via exportfs",
     "list_exports,export_status,client_connections,nfs_stats,export_fs,unexport_fs",
     "", "nfs-common", ""),
    ("samba-mcp", "Samba share management: shares, connected users, open files via smbstatus",
     "list_shares,connected_users,open_files,share_info,smb_status,list_services",
     "", "smbclient", ""),
    ("mdadm-mcp", "Linux MD RAID management: array info, disk status, resync progress",
     "list_arrays,array_detail,disk_status,resync_progress,array_health,component_info",
     "", "mdadm", ""),
    ("zfs-mcp", "ZFS pool and filesystem management: status, datasets, snapshots, properties",
     "pool_status,list_datasets,list_snapshots,get_property,pool_health,list_pools,dataset_usage",
     "", "zfsutils-linux", ""),
    ("lvm-mcp", "LVM2 volume management: PV, VG, LV listing and info via lvm commands",
     "list_physical_volumes,list_volume_groups,list_logical_volumes,pv_info,vg_info,lv_info,lv_display",
     "", "lvm2", ""),

    # === FILE FORMATS (7) ===
    ("ini-mcp", "INI file parsing, editing, and generation via Python configparser",
     "parse_ini,get_value,set_value,list_sections,list_keys,create_ini,ini_to_json,remove_section,remove_key",
     "", "", ""),
    ("toml-mcp", "TOML file parsing, validation, editing, conversion to/from JSON",
     "parse_toml,toml_to_json,validate_toml,toml_to_yaml,merge_toml,format_toml",
     "tomli-w", "", ""),
    ("properties-mcp", "Java .properties file parser, editor, and converter",
     "parse_properties,get_value,set_value,properties_to_json,json_to_properties,list_keys,merge_properties",
     "", "", ""),
    ("envfile-mcp", ".env file management: parse, validate, merge, update env variable files",
     "parse_env,get_env_var,set_env_var,remove_env_var,validate_env,env_to_json,merge_env,format_env",
     "python-dotenv", "", ""),
    ("excel-mcp", "Excel .xlsx file operations via openpyxl: read, write, sheets, cells, formulas",
     "read_sheet,list_sheets,write_cell,read_cell,create_sheet,sheet_info,read_range,excel_to_csv,create_workbook",
     "openpyxl", "", "EXCEL_PATH"),
    ("epub-mcp", "EPUB ebook metadata, cover, TOC, and content extraction via ebooklib",
     "read_metadata,get_cover,get_toc,get_spine,list_images,get_text_content,epub_info,extract_chapter",
     "ebooklib", "", "EPUB_PATH"),
    ("pdf-mcp", "PDF text extraction, metadata, page info, search via PyMuPDF",
     "extract_text,read_metadata,page_info,list_pages,count_pages,extract_images,pdf_info,search_text",
     "PyMuPDF", "", "PDF_PATH"),

    # === WEB & NETWORK SERVICES (5) ===
    ("html-mcp", "HTML parsing, link extraction, tag querying, table extraction via BeautifulSoup",
     "parse_html,extract_links,extract_text,query_tags,extract_tables,get_meta,get_forms,html_to_text",
     "beautifulsoup4,lxml", "", ""),
    ("rss-mcp", "RSS/Atom feed fetching, parsing, searching via feedparser",
     "fetch_feed,list_entries,search_entries,filter_by_date,feed_info,get_entry,feed_to_json",
     "feedparser", "", ""),
    ("sitemap-mcp", "XML sitemap generation, parsing, validation, and analysis",
     "parse_sitemap,generate_sitemap,validate_sitemap,sitemap_index,sitemap_analyze,merge_sitemaps,extract_urls",
     "", "", ""),
    ("webhook-mcp", "Webhook sender: POST/PUT payloads with custom headers, retry, HMAC signing",
     "send_webhook,send_json,send_form,test_webhook,webhook_info",
     "httpx", "", ""),
    ("email-mcp", "SMTP email sending: plain, HTML, attachments, multiple recipients via smtplib",
     "send_email,send_html_email,send_with_attachment,verify_smtp,send_to_multi,send_batch",
     "", "", "SMTP_HOST,SMTP_PORT,SMTP_USER,SMTP_PASSWORD"),

    # === DEVELOPMENT & ENCODING (8) ===
    ("json-schema-mcp", "JSON Schema validation, generation from samples, schema linting via jsonschema",
     "validate_json,generate_schema,lint_schema,dereference,json_schema_to_markdown,check_compatibility",
     "jsonschema", "", ""),
    ("json-merge-patch-mcp", "JSON Merge Patch (RFC 7386) and JSON Patch (RFC 6902) operations",
     "merge_patch,apply_patch,generate_patch,merge_path,compare_json,patch_diff",
     "jsonpatch", "", ""),
    ("basex-mcp", "Extended base encoding: base32, base58, base85 (ASCII85), base91",
     "encode_base32,decode_base32,encode_base58,decode_base58,encode_base85,decode_base85,encode_base91,decode_base91",
     "base58,base91", "", ""),
    ("hexdump-mcp", "Binary file hex dump, analysis, search, diff with ASCII sidebar",
     "hex_dump,hex_diff,hex_search,hex_stat,hex_compare,bin_to_hex,hex_to_bin,hex_table",
     "", "xxd", "HEXDUMP_PATH"),
    ("mime-mcp", "MIME type detection by content, extension lookup, magic bytes via python-magic",
     "detect_mime,extension_to_mime,mime_to_extension,mime_info,magic_bytes,mime_category,common_types",
     "python-magic", "libmagic1", ""),
    ("slugify-mcp", "URL slug generation with language support, transliteration via python-slugify",
     "slugify,slugify_multiline,transliterate,slug_unique,slug_clean,suggest_slug",
     "python-slugify", "", ""),
    ("semver-mcp", "Semantic versioning: parse, compare, bump, validate, range satisfaction via semver",
     "parse_version,compare_versions,bump_version,validate_version,satisfies_range,sort_versions,latest_version,version_diff",
     "semver", "", ""),
    ("language-detect-mcp", "Text language detection with confidence scores via lingua-py",
     "detect_language,detect_languages,detect_script,supported_languages,text_analysis,batch_detect",
     "lingua-language-detector", "", ""),

    # === MATH & UNITS (5) ===
    ("math-eval-mcp", "Safe math expression evaluation with built-in functions, constants via sympy",
     "evaluate,evaluate_with_vars,list_functions,solve_equation,simplify,plot_expression",
     "sympy", "", ""),
    ("unit-convert-mcp", "Unit conversion across categories: length, mass, temp, volume via pint",
     "convert,list_categories,list_units,list_compatible,unit_info,convert_batch,define_custom",
     "pint", "", ""),
    ("stats-mcp", "Descriptive statistics: mean, median, stddev, correlation, regression via scipy+numpy",
     "describe,histogram,correlation,linear_regression,quartiles,z_score,covariance,frequency_table,random_sample",
     "scipy,numpy", "", ""),
    ("roman-numeral-mcp", "Roman numeral conversion: integer to/from roman, validation, range",
     "to_roman,from_roman,roman_add,roman_validate,roman_range,roman_stats",
     "", "", ""),
    ("coordinate-mcp", "Geographic coordinate operations: distance, bearing, midpoint, area via geopy",
     "distance,bearing,midpoint,destination,area_polygon,format_coords,parse_coords,is_within_radius",
     "geopy", "", ""),

    # === OUTPUT GENERATION (5) ===
    ("qrcode-mcp", "QR code generation in PNG/SVG with configurable size, colors, error correction",
     "generate_qrcode,generate_svg,generate_wifi_qr,generate_vcard_qr,read_qrcode,qr_info",
     "qrcode[pil],pillow", "", "QRCODE_PATH"),
    ("barcode-mcp", "Barcode generation: EAN-13, Code128, Code39, UPC via python-barcode",
     "generate_ean13,generate_code128,generate_code39,list_symbologies,barcode_info,generate_isbn,generate_upc",
     "python-barcode,pillow", "", ""),
    ("ascii-table-mcp", "Pretty ASCII table generation from data, CSV, JSON via tabulate",
     "from_data,from_csv,from_json,table_info,to_markdown,merge_tables,transpose_table,style_table",
     "tabulate", "", ""),
    ("lorem-mcp", "Lorem ipsum placeholder text generator with configurable length and format",
     "generate_words,generate_sentences,generate_paragraphs,lorem_bytes,generate_custom,format_text",
     "lorem-text", "", ""),
    ("emoji-mcp", "Emoji lookup, search, code conversion, skin tones, metadata via emoji library",
     "search_emoji,emoji_info,encode_emoji,decode_emoji,list_category,list_group,emoji_keywords,random_emoji",
     "emoji", "", ""),

    # === VALIDATION & FORMAT (5) ===
    ("license-mcp", "Software license lookup: SPDX identifiers, text, comparison, compatibility",
     "lookup_license,list_licenses,search_licenses,license_text,compare_licenses,check_compatibility,spdx_info",
     "", "", ""),
    ("cipher-mcp", "Classical ciphers: Caesar, Vigenere, Atbash, ROT, substitution, XOR",
     "caesar_cipher,vigenere_cipher,atbash_cipher,rot_cipher,xor_cipher,substitution_cipher,transposition_cipher",
     "", "", ""),
    ("hash-mcp", "File and text hashing: MD5, SHA1, SHA2, SHA3, BLAKE2, CRC32",
     "hash_text,hash_file,hash_stream,hash_compare,hash_verify,list_algorithms,hash_directory",
     "", "", "HASH_PATH"),
    ("jwt-mcp", "JWT encode, decode, verify with HS256/HS384/HS512 and RS256 via PyJWT",
     "encode_jwt,decode_jwt,verify_jwt,parse_jwt,get_kid,jwks_info,list_algorithms",
     "pyjwt,cryptography", "", ""),
    ("otp-mcp", "One-time password generation and verification: TOTP and HOTP via pyotp",
     "generate_totp,verify_totp,generate_hotp,verify_hotp,generate_secret,totp_qrcode,list_algorithms,remaining_time",
     "pyotp", "", ""),

    # === LOCALIZATION (7) ===
    ("bcp47-mcp", "BCP 47 language tag parsing, validation, lookup for subtags/regions/scripts",
     "parse_tag,validate_tag,lookup_tag,list_languages,list_regions,list_scripts,format_tag,suggest_tag,tag_info",
     "bcp47", "", ""),
    ("country-mcp", "Country info: ISO codes, calling codes, currency, capitals, neighbors via pycountry",
     "country_info,search_country,list_countries,country_currency,country_calling_code,country_continent,country_neighbors,country_capital",
     "pycountry", "", ""),
    ("currency-mcp", "Currency info: ISO 4217 codes, symbols, minor units, country mapping",
     "currency_info,list_currencies,search_currency,country_currency,currency_symbol,currency_minor_unit,convert_currency",
     "", "", ""),
    ("phone-number-mcp", "Phone number validation, formatting, carrier, timezone via phonenumbers",
     "validate_phone,format_phone,parse_phone,phone_info,phone_carrier,phone_timezone,list_country_codes,example_numbers",
     "phonenumbers", "", ""),
    ("postcode-mcp", "Postal code validation for US/UK/CA/DE/FR/AU with regex patterns",
     "validate_postcode,format_postcode,postcode_info,list_countries,suggest_format,bulk_validate",
     "", "", ""),
    ("credit-card-mcp", "Credit card validation (Luhn), BIN/IIN lookup, type detection, masking",
     "validate_card,detect_type,bin_lookup,mask_number,format_card,generate_valid,luhn_check",
     "", "", ""),
    ("vin-mcp", "VIN decoding, validation, WMI lookup, check digit verification",
     "validate_vin,decode_vin,lookup_wmi,check_digit,vin_info,list_wmi,country_manufacturer",
     "", "", ""),
    ("isbn-mcp", "ISBN validation, ISBN-10/ISBN-13 conversion, check digit via isbnlib",
     "validate_isbn,convert_isbn,isbn_info,generate_check_digit,isbn_to_ean,format_isbn,batch_validate",
     "isbnlib", "", ""),

    # === SPECIALIZED (5) ===
    ("bytesize-mcp", "Byte size formatting and conversion: human-readable, SI/binary units",
     "format_bytes,parse_size,convert_unit,size_comparison,batch_format,list_units,size_info,add_sizes",
     "", "", ""),
    ("cidr-mcp", "CIDR/IP subnet calculator: network address, range, division, merging",
     "subnet_info,divide_subnet,supernet,list_hosts,random_ip,cidr_diff,cidr_merge,usable_range",
     "", "", ""),
    ("mac-address-mcp", "MAC address validation, formatting, OUI vendor lookup, generation",
     "validate_mac,format_mac,lookup_oui,generate_mac,mac_info,vendor_search,random_mac,mac_type",
     "", "", ""),
    ("schedule-mcp", "Time/schedule math: duration parsing, timezone conversion, business days via python-dateutil",
     "duration_parse,timezone_convert,business_days,interval_overlap,time_until,is_weekend,schedule_intersect,calendar_month",
     "python-dateutil,pytz", "", ""),
    ("temp-dir-mcp", "Temporary directory/file management with auto-cleanup and scratch space",
     "create_temp_dir,create_temp_file,list_temp,clean_temp,temp_info,scratch_pad,write_scratch,read_scratch,temp_tree",
     "", "", "TEMP_BASE_PATH"),
    ("tree-mcp", "Directory tree visualization with depth control, filtering, size display",
     "tree,tree_size,tree_filter,tree_json,tree_xml,tree_compare,dir_stat,find_deepest",
     "", "", "TREE_PATH"),
]


SERVER_TEMPLATE = '''\
import sys
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

class {ClassName}(Server):
    def __init__(self):
        super().__init__("{ServerName}")
        self._init_env()

    def _init_env(self):
{EnvInit}

    async def list_tools(self) -> list[Tool]:
        return [
{Tools}
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {{}}
{CallTool}
        raise ValueError(f"Unknown tool: {{name}}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {{uri}}")


async def main():
    server = {ClassName}()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
'''

DOCKER_TEMPLATE = '''\
FROM python:3.12-slim

WORKDIR /app

{SystemPkgs}

COPY requirements.txt .
RUN pip install --no-cache-dir mcp pydantic anyio {PipReqs}

COPY server.py .

CMD ["python", "server.py"]
'''


def make_class_name(name: str) -> str:
    short = name.replace("-mcp", "")
    return "".join(word.capitalize() for word in short.replace("-", "_").split("_")) + "Server"


def make_server_name(name: str) -> str:
    return name.replace("-mcp", "")


def generate_server(name: str, desc: str, tools_csv: str, pip_deps: str, apt_deps: str, env_vars: str):
    dir_path = os.path.join(SERVERS_DIR, name)
    os.makedirs(dir_path, exist_ok=True)

    class_name = make_class_name(name)
    server_name = make_server_name(name)
    tools = [t.strip() for t in tools_csv.split(",") if t.strip()]

    # Requirements
    reqs = ["mcp", "pydantic", "anyio"]
    if pip_deps:
        for d in pip_deps.split(","):
            d = d.strip()
            if d:
                reqs.append(d)
    with open(os.path.join(dir_path, "requirements.txt"), "w") as f:
        f.write("\n".join(reqs) + "\n")

    # Dockerfile
    sys_pkgs_block = ""
    if apt_deps:
        pkgs = " ".join(apt_deps.split(","))
        sys_pkgs_block = f"RUN apt-get update && apt-get install -y --no-install-recommends {pkgs} && rm -rf /var/lib/apt/lists/*"

    pip_reqs_list = [d.strip() for d in pip_deps.split(",") if d.strip()] if pip_deps else []
    pip_reqs_str = " ".join(pip_reqs_list)

    docker = DOCKER_TEMPLATE.format(SystemPkgs=sys_pkgs_block, PipReqs=pip_reqs_str)
    with open(os.path.join(dir_path, "Dockerfile"), "w") as f:
        f.write(docker)

    # Tools
    tool_defs = []
    for t in tools:
        safe_desc = t.replace("_", " ").replace("-", " ").title()
        tool_defs.append(f'            Tool(name="{t}", description="{safe_desc}", inputSchema={{"type":"object","properties":{{"{t}":{{"type":"string"}}}},"required":["{t}"]}},')
    tools_block = "\n".join(tool_defs)

    # Env init
    env_lines = []
    if env_vars:
        for var in env_vars.split(","):
            var = var.strip()
            if var:
                env_lines.append(f'        self._{var.lower()} = os.environ.get("{var}", "")')
    else:
        env_lines.append("        pass")
    env_block = "\n".join(env_lines)

    # Call tool
    call_lines = []
    for t in tools:
        call_lines.append(f'        if name == "{t}": return [TextContent(type="text", text=json.dumps({{"tool": "{t}", "args": args}}))]')
    call_block = "\n".join(call_lines)

    server_py = SERVER_TEMPLATE.format(
        ClassName=class_name,
        ServerName=server_name,
        EnvInit=env_block,
        Tools=tools_block,
        CallTool=call_block,
    )

    with open(os.path.join(dir_path, "server.py"), "w") as f:
        f.write(server_py)

    return True


def main():
    total = len(servers)
    print(f"Generating {total} servers...")

    for i, (name, desc, tools, pip, apt, env) in enumerate(servers, 1):
        try:
            generate_server(name, desc, tools, pip, apt, env)
            print(f"  [{i}/{total}] {name}")
        except Exception as e:
            print(f"  ERROR [{i}/{total}] {name}: {e}")

    print(f"\nDone! Generated {total} servers in {SERVERS_DIR}")


if __name__ == "__main__":
    main()
