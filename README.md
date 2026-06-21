# Unraid MCP Servers — 106 Model Context Protocol Servers for Unraid

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Repo](https://img.shields.io/badge/GitHub-unraid--mcp--servers-blue.svg)](https://github.com/wildfirebill-unraid/unraid-mcp-servers)
[![Servers](https://img.shields.io/badge/Servers-106-green.svg)](#-server-catalog)
[![Unraid](https://img.shields.io/badge/Unraid-MCP-orange.svg)](#)

A comprehensive collection of 106 MCP (Model Context Protocol) servers for Unraid, enabling LLMs like Claude, ChatGPT, and other AI agents to interact with your Unraid system — databases, files, network, media, system resources, and more.

## What is MCP?

The Model Context Protocol (MCP) lets AI agents securely access tools, data, and resources on your system. Each server in this collection exposes a focused set of capabilities — query a PostgreSQL database, search files, check system health, send emails, or manage Docker containers — all through natural language.

## Why This Collection?

Instead of hunting down individual MCP servers across GitHub, this single catalog gives you:

- **106 ready-to-run servers** across databases, networking, system administration, media, data formats, and developer utilities
- **Unraid-native** — each server builds and deploys inside Docker on Unraid
- **One config source** — all environment variables documented in a single `.env.example`
- **Catalog-ready** — `unraid-catalog.yml` works with the Unraid MCP plugin for one-click activation

## Quick Start — Deploy via MCP Gateway

Deploy these servers through [mcp-gateway-unraid](https://github.com/wildfirebill-unraid/mcp-gateway-unraid) — an MCP gateway that spawns each server as an isolated Docker container on your Unraid box.

```bash
# 1. Install the gateway (see gateway repo for details)
# 2. Mount unraid-catalog.yml into the gateway container
# 3. Set which servers to enable:
GATEWAY_SERVERS=filesystem-mcp,sqlite-mcp,postgresql-mcp,github-mcp

# 4. Connect any MCP client (Claude Desktop, VS Code, Cursor)
#    to http://<unraid-ip>:8811/mcp with your auth token
```

> **You don't add servers one at a time.** The entire catalog (all 106
> servers) is registered at once. Pick only the ones you actually need
> via `GATEWAY_SERVERS` — the gateway only spins up containers for those.
> Enabling all 106 at once will exhaust your system resources.

## Server Catalog

### Core
| Server | Description |
|--------|-------------|
| **filesystem-mcp** | Read, write, search, browse files on Unraid shares |
| **system-info-mcp** | CPU, memory, disk, network, process info |
| **docker-mcp** | Manage Docker containers and images |
| **sqlite-mcp** | Query and manage SQLite databases |
| **git-mcp** | Git repository inspection and operations |
| **github-mcp** | GitHub API — issues, PRs, repos, files, search |
| **mempalace-mcp** | Persistent vector database for AI agent memory |

### Databases
PostgreSQL, MySQL, MongoDB, Redis, Elasticsearch, InfluxDB, Memcached

### Network & Security
DNS resolver, traceroute, port scanner, nmap-lite, WireGuard, fail2ban, firewall, SSL/TLS, CIDR/IP tools, net-connections

### System Administration
Process management, services, cron/scheduling, log viewer, kernel info, ZFS, LVM, mdadm, Samba, NFS, user/group management, packages, temp-dir, envfile

### Data Formats
CSV, XML, YAML, JSON schema, JSON merge patch, TOML, INI, HTML, markdown, properties, template engine

### Developer Utilities
Hash (SHA/MD5), UUID, JWT, barcode, QR code, base encoding, hex dump, slugify, semver, diff, sort, color, HTML minify, text utility, regex

### Media & Documents
Image info, media info, media convert, PDF, Excel, EPUB, archive, backup

### Communications
Email (SMTP), webhook

### Utility (Standalone)
ASCII table, bcp47, bytesize, cipher, coordinate, country, credit card validation, currency, emoji, ISBN, language detection, license lookup, lorem ipsum, MAC address, math evaluator, MIME type, OTP, phone number, postcode, Roman numerals, RSS, sitemap, stats, unit converter, VIN decoder, weather

## Environment Variables

All configuration lives in `.env.example`. Key patterns:

```env
# Database servers
#PGHOST=localhost        # PostgreSQL
#MYSQL_HOST=localhost    # MySQL
#REDIS_HOST=localhost    # Redis
#MONGODB_URI=...         # MongoDB

# Network services
#SMTP_HOST=smtp.example.com  # Email
#WEBHOOK_TIMEOUT=30          # Webhook

# Authentication
#GITHUB_TOKEN=ghp_...        # GitHub API

# File paths (default base: /mnt/user/data/mcp/)
#FILESYSTEM_ALLOWED_PATH=/mnt/user
```

## Architecture

```
servers/               # 106 individual server directories
├── filesystem-mcp/    # Dockerfile + server.py
├── sqlite-mcp/
├── github-mcp/
└── ...

unraid-catalog.yml     # MCP Gateway catalog — all 106 servers defined here
.env.example           # All configurable environment variables
docker-compose.yml     # Docker Compose orchestration
```

## Gateway

The [mcp-gateway-unraid](https://github.com/wildfirebill-unraid/mcp-gateway-unraid)
project runs the gateway that loads this catalog. Pass `--catalog=/path/to/unraid-catalog.yml` to register all 106 servers, then use `GATEWAY_SERVERS` to enable a subset.

## Adding a New Server

1. Create `servers/<name>/Dockerfile` and source files
2. Add a `servers/<name>:` entry to `unraid-catalog.yml`
3. Add new env vars to `.env.example`

See existing server directories for reference patterns.

## License

MIT
