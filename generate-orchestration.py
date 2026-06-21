#!/usr/bin/env python3
"""Generate build-all.ps1, docker-compose.yml, unraid-catalog.yml, .env.example for all MCP servers."""

import os

SERVERS_DIR = r"G:\zed\unraid_mcp_servers\servers"

# ---- ALL SERVERS (existing 30 + 74 new = 104) ----
# Format: (directory_name, has_path_env, needs_docker_sock, needs_privileged, needs_pid_host, 
#           needs_dbus, extra_volumes, env_vars_for_catalog, catalog_props)
# Server definitions: name, has_file_path (needs /mnt/user mount + path env), special flags...

SERVERS = [
    # === EXISTING 30 (preserved with original descriptions) ===
    ("filesystem-mcp", True, False, False, False, False, [], 
     [("FILESYSTEM_ALLOWED_PATH", "Root path the server can access")]),
    ("system-info-mcp", False, False, True, True, False, [],
     []),
    ("sqlite-mcp", True, False, False, False, False, [],
     [("SQLITE_DB_DIR", "Directory containing .db files")]),
    ("docker-mcp", False, True, False, False, False, [],
     [("DOCKER_HOST", "Docker socket path")]),
    ("check-host-mcp", False, False, False, False, False, [],
     []),
    ("text-utility-mcp", False, False, False, False, False, [],
     []),
    ("media-info-mcp", True, False, False, False, False, [],
     [("MEDIA_INFO_PATH", "Root path for media files")]),
    ("media-convert-mcp", True, False, False, False, False, [],
     [("MEDIA_CONVERT_PATH", "Root path for media files")]),
    ("archive-mcp", True, False, False, False, False, [],
     [("ARCHIVE_PATH", "Root path for archive operations")]),
    ("backup-mcp", True, False, False, False, False, [],
     [("BACKUP_SOURCE", "Source directory"), ("BACKUP_DEST", "Destination directory")]),
    ("process-mcp", False, False, True, True, False, [],
     []),
    ("log-mcp", True, False, False, False, False, [("/var/log:/var/log:ro",)],
     [("LOG_PATH", "Root path for log files")]),
    ("yaml-mcp", False, False, False, False, False, [],
     []),
    ("xml-mcp", False, False, False, False, False, [],
     []),
    ("diff-mcp", True, False, False, False, False, [],
     []),
    ("image-mcp", True, False, False, False, False, [],
     [("IMAGE_PATH", "Root path for image files")]),
    ("git-mcp", True, False, False, False, False, [],
     [("GIT_REPO_PATH", "Root path for git repositories")]),
    ("ssl-mcp", False, False, False, False, False, [],
     []),
    ("service-mcp", False, False, True, False, True, [],
     []),
    ("cron-mcp", False, False, False, False, False, [],
     []),
    ("csv-mcp", True, False, False, False, False, [],
     [("CSV_PATH", "Root path for CSV files")]),
    ("template-mcp", True, False, False, False, False, [],
     [("TEMPLATE_PATH", "Root path for template files")]),
    ("password-mcp", False, False, False, False, False, [],
     []),
    ("uuid-mcp", False, False, False, False, False, [],
     []),
    ("color-mcp", False, False, False, False, False, [],
     []),
    ("ipcalc-mcp", False, False, False, False, False, [],
     []),
    ("sort-mcp", False, False, False, False, False, [],
     []),
    ("finder-mcp", True, False, False, False, False, [],
     [("FINDER_PATH", "Root path for file searches")]),
    ("encoding-mcp", True, False, False, False, False, [],
     [("ENCODING_PATH", "Root path for files to analyze")]),
    ("markdown-mcp", False, False, False, False, False, [],
     []),

    # === NEW 74 ===
    ("postgresql-mcp", False, False, False, False, False, [],
     [("PGHOST", "PostgreSQL host"), ("PGPORT", "Port"), ("PGUSER", "User"), 
      ("PGPASSWORD", "Password"), ("PGDATABASE", "Database name")]),
    ("mysql-mcp", False, False, False, False, False, [],
     [("MYSQL_HOST", "MySQL host"), ("MYSQL_PORT", "Port"), ("MYSQL_USER", "User"),
      ("MYSQL_PASSWORD", "Password"), ("MYSQL_DATABASE", "Database name")]),
    ("redis-mcp", False, False, False, False, False, [],
     [("REDIS_HOST", "Redis host"), ("REDIS_PORT", "Port"), ("REDIS_PASSWORD", "Password"), ("REDIS_DB", "DB number")]),
    ("mongodb-mcp", False, False, False, False, False, [],
     [("MONGODB_URI", "Connection URI"), ("MONGODB_DATABASE", "Database name")]),
    ("elasticsearch-mcp", False, False, False, False, False, [],
     [("ES_HOST", "Elasticsearch host"), ("ES_PORT", "Port")]),
    ("influxdb-mcp", False, False, False, False, False, [],
     [("INFLUXDB_URL", "InfluxDB URL"), ("INFLUXDB_TOKEN", "Token"), ("INFLUXDB_ORG", "Organization")]),
    ("memcached-mcp", False, False, False, False, False, [],
     [("MEMCACHED_HOST", "Memcached host"), ("MEMCACHED_PORT", "Port")]),
    ("port-scanner-mcp", False, False, False, False, False, [], []),
    ("dns-resolver-mcp", False, False, False, False, False, [], []),
    ("traceroute-mcp", False, False, False, False, False, [], []),
    ("net-connections-mcp", False, False, False, False, False, [], []),
    ("fail2ban-mcp", False, False, True, False, False, [],
     []),
    ("wireguard-mcp", False, False, True, False, False, [],
     []),
    ("nmap-lite-mcp", False, False, False, False, False, [], []),
    ("geo-ip-mcp", False, False, False, False, False, [],
     [("GEOIP_DB_PATH", "Path to GeoLite2 databases")]),
    ("firewall-mcp", False, False, True, False, False, [],
     []),
    ("journald-mcp", False, False, False, False, False, [
     "/var/log/journal:/var/log/journal:ro",
    ], []),
    ("users-groups-mcp", False, False, False, False, False, [], []),
    ("packages-mcp", False, False, False, False, False, [], []),
    ("kernel-mcp", False, False, False, False, False, [], []),
    ("nfs-mcp", False, False, False, False, False, [], []),
    ("samba-mcp", False, False, False, False, False, [], []),
    ("mdadm-mcp", False, False, True, False, False, [
     "/dev:/dev:ro",
    ], []),
    ("zfs-mcp", False, False, True, False, False, [
     "/dev/zfs:/dev/zfs:ro",
    ], []),
    ("lvm-mcp", False, False, True, False, False, [
     "/dev:/dev:ro",
    ], []),
    ("ini-mcp", False, False, False, False, False, [], []),
    ("toml-mcp", False, False, False, False, False, [], []),
    ("properties-mcp", False, False, False, False, False, [], []),
    ("envfile-mcp", True, False, False, False, False, [],
     [("ENVFILE_PATH", "Root path for .env files")]),
    ("excel-mcp", True, False, False, False, False, [],
     [("EXCEL_PATH", "Root path for Excel files")]),
    ("epub-mcp", True, False, False, False, False, [],
     [("EPUB_PATH", "Root path for EPUB files")]),
    ("pdf-mcp", True, False, False, False, False, [],
     [("PDF_PATH", "Root path for PDF files")]),
    ("html-mcp", True, False, False, False, False, [], []),
    ("rss-mcp", False, False, False, False, False, [], []),
    ("sitemap-mcp", True, False, False, False, False, [], []),
    ("webhook-mcp", False, False, False, False, False, [], []),
    ("email-mcp", False, False, False, False, False, [],
     [("SMTP_HOST", "SMTP server host"), ("SMTP_PORT", "SMTP port"), 
      ("SMTP_USER", "SMTP user"), ("SMTP_PASSWORD", "SMTP password")]),
    ("json-schema-mcp", False, False, False, False, False, [], []),
    ("json-merge-patch-mcp", False, False, False, False, False, [], []),
    ("basex-mcp", False, False, False, False, False, [], []),
    ("hexdump-mcp", True, False, False, False, False,
     [("/dev:/dev:ro",)],
     [("HEXDUMP_PATH", "Root path for binary files")]),
    ("mime-mcp", True, False, False, False, False, [], []),
    ("slugify-mcp", False, False, False, False, False, [], []),
    ("semver-mcp", False, False, False, False, False, [], []),
    ("language-detect-mcp", False, False, False, False, False, [], []),
    ("math-eval-mcp", False, False, False, False, False, [], []),
    ("unit-convert-mcp", False, False, False, False, False, [], []),
    ("stats-mcp", False, False, False, False, False, [], []),
    ("roman-numeral-mcp", False, False, False, False, False, [], []),
    ("coordinate-mcp", False, False, False, False, False, [], []),
    ("qrcode-mcp", True, False, False, False, False, [],
     [("QRCODE_PATH", "Output path for QR codes")]),
    ("barcode-mcp", True, False, False, False, False, [], []),
    ("ascii-table-mcp", False, False, False, False, False, [], []),
    ("lorem-mcp", False, False, False, False, False, [], []),
    ("emoji-mcp", False, False, False, False, False, [], []),
    ("license-mcp", False, False, False, False, False, [], []),
    ("cipher-mcp", False, False, False, False, False, [], []),
    ("hash-mcp", True, False, False, False, False, [],
     [("HASH_PATH", "Root path for file hashing")]),
    ("jwt-mcp", False, False, False, False, False, [], []),
    ("otp-mcp", False, False, False, False, False, [], []),
    ("bcp47-mcp", False, False, False, False, False, [], []),
    ("country-mcp", False, False, False, False, False, [], []),
    ("currency-mcp", False, False, False, False, False, [], []),
    ("phone-number-mcp", False, False, False, False, False, [], []),
    ("postcode-mcp", False, False, False, False, False, [], []),
    ("credit-card-mcp", False, False, False, False, False, [], []),
    ("vin-mcp", False, False, False, False, False, [], []),
    ("isbn-mcp", False, False, False, False, False, [], []),
    ("bytesize-mcp", False, False, False, False, False, [], []),
    ("cidr-mcp", False, False, False, False, False, [], []),
    ("mac-address-mcp", False, False, False, False, False, [], []),
    ("schedule-mcp", False, False, False, False, False, [], []),
    ("temp-dir-mcp", False, False, False, False, False, [],
     [("TEMP_BASE_PATH", "Base path for temp operations")]),
    ("tree-mcp", True, False, False, False, False, [],
     [("TREE_PATH", "Root path for tree operations")]),
]

CATALOG_DESCRIPTIONS = {
    "postgresql-mcp": "PostgreSQL database querying and schema inspection via psycopg2",
    "mysql-mcp": "MySQL/MariaDB database operations via PyMySQL",
    "redis-mcp": "Redis key-value operations: get, set, delete, keys, server info via redis-py",
    "mongodb-mcp": "MongoDB document database operations via PyMongo",
    "elasticsearch-mcp": "Elasticsearch cluster operations via elasticsearch-py",
    "influxdb-mcp": "InfluxDB time series operations via influxdb-client",
    "memcached-mcp": "Memcached operations via pymemcache",
    "port-scanner-mcp": "TCP port scanning with connect scan, service detection, banner grabbing",
    "dns-resolver-mcp": "DNS record lookups: A, AAAA, MX, TXT, NS, CNAME, SOA, SRV via dnspython",
    "traceroute-mcp": "Network path tracing with per-hop timing and path analysis",
    "net-connections-mcp": "Active network connections, listening sockets, interface stats via psutil",
    "fail2ban-mcp": "Fail2ban jail management: status, ban/unban IPs, log tail",
    "wireguard-mcp": "WireGuard VPN interface management: peer status, handshake times, config",
    "nmap-lite-mcp": "Python-based network discovery: ping sweep, port scan, service enumeration",
    "geo-ip-mcp": "IP geolocation using local MaxMind GeoLite2 database via geoip2",
    "firewall-mcp": "Linux iptables/nftables firewall: list rules, chains, policy info",
    "journald-mcp": "Systemd journal reader: query logs by unit, priority, time range, boot",
    "users-groups-mcp": "User and group management: list, info, group members, login history",
    "packages-mcp": "Package management: list installed, search, info, dependency tree via dpkg/rpm",
    "kernel-mcp": "Kernel parameters via sysctl and kernel module management",
    "nfs-mcp": "NFS server export management: exports, clients, status",
    "samba-mcp": "Samba share management: shares, connected users, open files via smbstatus",
    "mdadm-mcp": "Linux MD RAID management: array info, disk status, resync progress",
    "zfs-mcp": "ZFS pool and filesystem management: status, datasets, snapshots, properties",
    "lvm-mcp": "LVM2 volume management: PV, VG, LV listing and info via lvm commands",
    "ini-mcp": "INI file parsing, editing, and generation via Python configparser",
    "toml-mcp": "TOML file parsing, validation, editing, conversion to/from JSON",
    "properties-mcp": "Java .properties file parser, editor, and converter",
    "envfile-mcp": ".env file management: parse, validate, merge, update env variable files",
    "excel-mcp": "Excel .xlsx file operations via openpyxl: read, write, sheets, cells, formulas",
    "epub-mcp": "EPUB ebook metadata, cover, TOC, and content extraction via ebooklib",
    "pdf-mcp": "PDF text extraction, metadata, page info, search via PyMuPDF",
    "html-mcp": "HTML parsing, link extraction, tag querying, table extraction via BeautifulSoup",
    "rss-mcp": "RSS/Atom feed fetching, parsing, searching via feedparser",
    "sitemap-mcp": "XML sitemap generation, parsing, validation, and analysis",
    "webhook-mcp": "Webhook sender: POST/PUT payloads with custom headers, retry, HMAC signing",
    "email-mcp": "SMTP email sending: plain, HTML, attachments, multiple recipients",
    "json-schema-mcp": "JSON Schema validation, generation from samples, schema linting",
    "json-merge-patch-mcp": "JSON Merge Patch (RFC 7386) and JSON Patch (RFC 6902) operations",
    "basex-mcp": "Extended base encoding: base32, base58, base85 (ASCII85), base91",
    "hexdump-mcp": "Binary file hex dump, analysis, search, diff with ASCII sidebar",
    "mime-mcp": "MIME type detection by content, extension lookup, magic bytes via python-magic",
    "slugify-mcp": "URL slug generation with language support, transliteration",
    "semver-mcp": "Semantic versioning: parse, compare, bump, validate, range satisfaction",
    "language-detect-mcp": "Text language detection with confidence scores via lingua-py",
    "math-eval-mcp": "Safe math expression evaluation with built-in functions via sympy",
    "unit-convert-mcp": "Unit conversion: length, mass, temp, volume, speed via pint",
    "stats-mcp": "Descriptive statistics: mean, median, stddev, correlation, regression",
    "roman-numeral-mcp": "Roman numeral conversion: integer to/from roman, validation",
    "coordinate-mcp": "Geographic coordinate operations: distance, bearing, midpoint via geopy",
    "qrcode-mcp": "QR code generation in PNG/SVG with configurable size, error correction",
    "barcode-mcp": "Barcode generation: EAN-13, Code128, Code39, UPC via python-barcode",
    "ascii-table-mcp": "Pretty ASCII table generation from data, CSV, JSON via tabulate",
    "lorem-mcp": "Lorem ipsum placeholder text generator with configurable length",
    "emoji-mcp": "Emoji lookup, search, code conversion, skin tones, metadata",
    "license-mcp": "Software license lookup: SPDX identifiers, text, comparison",
    "cipher-mcp": "Classical ciphers: Caesar, Vigenere, Atbash, ROT, substitution",
    "hash-mcp": "File and text hashing: MD5, SHA1, SHA2, SHA3, BLAKE2, CRC32",
    "jwt-mcp": "JWT encode, decode, verify with HS256/HS384/HS512 via PyJWT",
    "otp-mcp": "One-time password generation and verification: TOTP and HOTP via pyotp",
    "bcp47-mcp": "BCP 47 language tag parsing, validation, lookup for subtags/regions",
    "country-mcp": "Country info: ISO codes, calling codes, currency, capitals via pycountry",
    "currency-mcp": "Currency info: ISO 4217 codes, symbols, minor units, country mapping",
    "phone-number-mcp": "Phone number validation, formatting, carrier, timezone via phonenumbers",
    "postcode-mcp": "Postal code validation for US/UK/CA/DE/FR/AU with regex patterns",
    "credit-card-mcp": "Credit card validation (Luhn), BIN/IIN lookup, type detection",
    "vin-mcp": "VIN decoding, validation, WMI lookup, check digit verification",
    "isbn-mcp": "ISBN validation, ISBN-10/ISBN-13 conversion, check digit via isbnlib",
    "bytesize-mcp": "Byte size formatting: human-readable, SI/binary units, parsing, comparison",
    "cidr-mcp": "CIDR/IP subnet calculator: network address, range, division, merging",
    "mac-address-mcp": "MAC address validation, formatting, OUI vendor lookup, generation",
    "schedule-mcp": "Time/schedule math: duration parsing, timezone conversion, business days",
    "temp-dir-mcp": "Temporary directory/file management with auto-cleanup",
    "tree-mcp": "Directory tree visualization with depth control, filtering, size display",
}


def generate_build_script():
    names = [s[0] for s in SERVERS]
    parts = []
    for i in range(0, len(names), 6):
        chunk = names[i:i+6]
        parts.append("    " + ",".join(f'"{n}"' for n in chunk))

    content = '''$servers = @(
%s
)

$tag = if ($args[0]) { $args[0] } else { "latest" }

foreach ($s in $servers) {
    Write-Host "Building $s:$tag ..." -ForegroundColor Cyan
    docker build -t "unraid-mcp/$s`:$tag" -f "servers/$s/Dockerfile" "servers/$s/"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $s" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`nAll %d builds succeeded!" -ForegroundColor Green
Write-Host "`nImages:" -ForegroundColor Yellow
docker images --filter "reference=unraid-mcp/*" --format "table {{.Repository}}\\t{{.Tag}}\\t{{.Size}}"
''' % (",\n".join(parts), len(names))

    path = r"G:\zed\unraid_mcp_servers\build-all.ps1"
    with open(path, "w") as f:
        f.write(content)
    print(f"Wrote {path} ({len(names)} servers)")


def generate_docker_compose():
    lines = ['version: "3.8"\n', "", "services:"]
    
    for name, has_path, needs_docker, needs_priv, needs_pid, needs_dbus, extra_vols, _ in SERVERS:
        short = name.replace("-mcp", "")
        hostname = f"unraid-mcp-{short}"
        
        lines.append(f"  {name}:")
        lines.append(f"    build: ./servers/{name}")
        lines.append(f"    image: unraid-mcp/{name}:latest")
        lines.append(f"    container_name: {hostname}")
        
        # Volumes
        vols = []
        if has_path or name in ("backup-mcp",):
            if name == "backup-mcp":
                vols.append("/mnt/user:/data")
                vols.append("/mnt/user/backups:/backup")
            else:
                vols.append("/mnt/user:/data")
        if needs_docker:
            vols.append("/var/run/docker.sock:/var/run/docker.sock")
        if needs_dbus:
            vols.append("/run/dbus:/run/dbus:ro")
        vols.extend(extra_vols)
        
        if vols:
            lines.append("    volumes:")
            for v in vols:
                lines.append(f"      - {v}")
            # Add env var for path-based servers
            if has_path:
                env_name = {
                    "sqlite-mcp": "SQLITE_DB_DIR",
                    "media-info-mcp": "MEDIA_INFO_PATH",
                    "media-convert-mcp": "MEDIA_CONVERT_PATH",
                    "archive-mcp": "ARCHIVE_PATH",
                    "backup-mcp": "BACKUP_SOURCE",
                    "log-mcp": "LOG_PATH",
                    "image-mcp": "IMAGE_PATH",
                    "git-mcp": "GIT_REPO_PATH",
                    "csv-mcp": "CSV_PATH",
                    "template-mcp": "TEMPLATE_PATH",
                    "finder-mcp": "FINDER_PATH",
                    "encoding-mcp": "ENCODING_PATH",
                    "excel-mcp": "EXCEL_PATH",
                    "epub-mcp": "EPUB_PATH",
                    "pdf-mcp": "PDF_PATH",
                    "qrcode-mcp": "QRCODE_PATH",
                    "hash-mcp": "HASH_PATH",
                    "hexdump-mcp": "HEXDUMP_PATH",
                    "tree-mcp": "TREE_PATH",
                    "filesystem-mcp": "FILESYSTEM_ALLOWED_PATH",
                }.get(name, "").upper()
                if env_name:
                    lines.append("    environment:")
                    lines.append(f"      - {env_name}=/data")
        
        # Privileged
        if needs_priv:
            lines.append("    privileged: true")
        if needs_pid:
            lines.append('    pid: "host"')
        
        lines.append("    stdin_open: true")
        lines.append("    tty: true")
        lines.append("")
    
    path = r"G:\zed\unraid_mcp_servers\docker-compose.yml"
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {path}")


def generate_catalog():
    lines = ["version: 3", 'name: unraid-mcp', 'displayName: Unraid MCP Toolset', "servers:"]
    
    for name, _, _, _, _, _, _, env_vars in SERVERS:
        desc = CATALOG_DESCRIPTIONS.get(name, f"{name} server")
        title = " ".join(p.capitalize() for p in name.replace("-mcp", "").replace("-", " ").split())
        
        lines.append(f"  {name}:")
        lines.append(f'    description: "{desc}"')
        lines.append(f'    title: "{title}"')
        lines.append('    type: "server"')
        lines.append(f'    image: "unraid-mcp/{name}:latest"')
        
        if env_vars:
            lines.append("    env:")
            for var, desc_var in env_vars:
                lines.append(f'      - name: "{var}"')
                lines.append(f'        value: "{{{{{name}.{var.lower()}}}}}"')
        
        lines.append("    command:")
        lines.append('      - "--transport=stdio"')
        
        conf_desc = f"{title} configuration"
        lines.append("    config:")
        lines.append(f'      - name: "{name}"')
        lines.append(f'        description: "{conf_desc}"')
        lines.append('        type: "object"')
        lines.append("        properties:")
        if env_vars:
            for var, desc_var in env_vars:
                vname = var.lower().replace(name.replace("-mcp","").lower() + "_", "", 1) if var.lower().startswith(name.replace("-mcp","").lower() + "_") else var.lower()
                lines.append(f"          {var.lower()}:")
                lines.append(f'            type: "string"')
                lines.append(f'            description: "{desc_var}"')
                lines.append(f'            default: ""')
        else:
            lines.append("          {}:")
        lines.append("        required: []")
        lines.append("")
    
    path = r"G:\zed\unraid_mcp_servers\unraid-catalog.yml"
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {path}")


def generate_env_example():
    lines = [
        "# Unraid MCP Servers Configuration",
        "# Copy to .env and adjust paths for your system",
        "",
    ]
    
    seen = set()
    for name, has_path, _, _, _, _, _, env_vars in SERVERS:
        if has_path and name not in seen:
            if name == "filesystem-mcp":
                lines.append("# Filesystem MCP: root path the server can access")
                lines.append("FILESYSTEM_ALLOWED_PATH=/mnt/user")
                lines.append("")
            elif name == "sqlite-mcp":
                lines.append("# SQLite MCP: directory containing .db files")
                lines.append("SQLITE_DB_DIR=/mnt/user/appdata")
                lines.append("")
            elif name == "docker-mcp":
                lines.append("# Docker MCP: docker socket path")
                lines.append("DOCKER_HOST=unix:///var/run/docker.sock")
                lines.append("")
            elif name == "media-info-mcp":
                lines.append("# Media Info/Convert MCP: root path for media files")
                lines.append("MEDIA_INFO_PATH=/mnt/user/media")
                lines.append("MEDIA_CONVERT_PATH=/mnt/user/media")
                lines.append("")
            elif name == "backup-mcp":
                lines.append("# Backup MCP: source and destination directories")
                lines.append("BACKUP_SOURCE=/mnt/user")
                lines.append("BACKUP_DEST=/mnt/user/backups")
                lines.append("")
            elif name == "log-mcp":
                lines.append("# Log MCP: root path for log files")
                lines.append("LOG_PATH=/mnt/user/logs")
                lines.append("")
            elif name == "csv-mcp":
                lines.append("# CSV MCP: root path for CSV files")
                lines.append("CSV_PATH=/mnt/user")
                lines.append("")
            elif name == "template-mcp":
                lines.append("# Template MCP: root path for template files")
                lines.append("TEMPLATE_PATH=/mnt/user")
                lines.append("")
            elif name == "image-mcp":
                lines.append("# Image MCP: root path for image files")
                lines.append("IMAGE_PATH=/mnt/user")
                lines.append("")
            elif name == "git-mcp":
                lines.append("# Git MCP: root path for git repositories")
                lines.append("GIT_REPO_PATH=/mnt/user/git")
                lines.append("")
            elif name == "finder-mcp":
                lines.append("# Finder MCP: root path for file searches")
                lines.append("FINDER_PATH=/mnt/user")
                lines.append("")
            elif name == "encoding-mcp":
                lines.append("# Encoding MCP: root path for files to analyze")
                lines.append("ENCODING_PATH=/mnt/user")
                lines.append("")
            elif name == "pdf-mcp":
                lines.append("# PDF MCP: root path for PDF files")
                lines.append("PDF_PATH=/mnt/user")
                lines.append("")
            elif name == "excel-mcp":
                lines.append("# Excel MCP: root path for Excel files")
                lines.append("EXCEL_PATH=/mnt/user")
                lines.append("")
            elif name == "epub-mcp":
                lines.append("# EPUB MCP: root path for EPUB files")
                lines.append("EPUB_PATH=/mnt/user")
                lines.append("")
            elif name == "qrcode-mcp":
                lines.append("# QR Code MCP: output path for QR codes")
                lines.append("QRCODE_PATH=/mnt/user")
                lines.append("")
            elif name == "hash-mcp":
                lines.append("# Hash MCP: root path for file hashing")
                lines.append("HASH_PATH=/mnt/user")
                lines.append("")
            elif name == "tree-mcp":
                lines.append("# Tree MCP: root path for tree operations")
                lines.append("TREE_PATH=/mnt/user")
                lines.append("")
            elif name == "hexdump-mcp":
                lines.append("# Hexdump MCP: root path for binary files")
                lines.append("HEXDUMP_PATH=/mnt/user")
                lines.append("")
            elif name == "archive-mcp":
                lines.append("# Archive MCP: root path for archive operations")
                lines.append("ARCHIVE_PATH=/mnt/user")
                lines.append("")
            elif name == "envfile-mcp":
                lines.append("# Envfile MCP: root path for .env files")
                lines.append("ENVFILE_PATH=/mnt/user")
                lines.append("")
            seen.add(name)
        
        if env_vars and name not in seen:
            for var, desc_var in env_vars:
                if var not in seen:
                    lines.append(f"# {name}: {desc_var}")
                    lines.append(f"{var}=localhost")
                    lines.append("")
                    seen.add(var)
    
    # Add database service env vars
    db_vars = {
        "PGHOST": "localhost",
        "PGPORT": "5432", 
        "PGUSER": "postgres",
        "PGDATABASE": "postgres",
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "root",
        "MYSQL_DATABASE": "mysql",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6379",
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DATABASE": "admin",
        "ES_HOST": "localhost",
        "ES_PORT": "9200",
        "INFLUXDB_URL": "http://localhost:8086",
        "INFLUXDB_ORG": "myorg",
        "MEMCACHED_HOST": "localhost",
        "MEMCACHED_PORT": "11211",
        "GEOIP_DB_PATH": "/var/lib/GeoIP",
        "SMTP_HOST": "localhost",
        "SMTP_PORT": "587",
    }
    
    # Remove vars already added
    existing = set(seen)
    remaining = {k: v for k, v in db_vars.items() if k not in existing}
    
    if remaining:
        for k, v in remaining.items():
            lines.append(f"# {k}")
            lines.append(f"{k}={v}")
            lines.append("")
    
    path = r"G:\zed\unraid_mcp_servers\.env.example"
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {path}")


def verify_servers():
    """Check all server directories exist."""
    expected = set(s[0] for s in SERVERS)
    actual = set()
    if os.path.isdir(SERVERS_DIR):
        for d in os.listdir(SERVERS_DIR):
            dpath = os.path.join(SERVERS_DIR, d)
            if os.path.isdir(dpath) and os.path.exists(os.path.join(dpath, "server.py")):
                actual.add(d)
    
    missing = expected - actual
    extra = actual - expected
    
    if missing:
        print(f"ERROR: {len(missing)} servers missing: {sorted(missing)}")
    else:
        print(f"All {len(expected)} servers present in {SERVERS_DIR}")
    
    if extra:
        print(f"Note: {len(extra)} extra directories: {sorted(extra)}")
    
    return len(missing) == 0, missing


def main():
    print("Generating orchestration files for 104 MCP servers...\n")
    generate_build_script()
    generate_docker_compose()
    generate_catalog()
    generate_env_example()
    print("\n--- Verification ---")
    ok, missing = verify_servers()
    print(f"\nAll files generated successfully!" if ok else f"\nMissing {len(missing)} servers!")


if __name__ == "__main__":
    main()
