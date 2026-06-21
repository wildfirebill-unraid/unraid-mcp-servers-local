param([switch]$Run)

if (-not $Run) {
    Write-Host "This script will generate 69 MCP servers. Run with -Run to execute." -ForegroundColor Yellow
    exit
}

$servers = @(
    # === DATABASE ===
    @{Name="postgresql-mcp"; Desc="PostgreSQL database querying and schema inspection via psycopg2"; Tools="list_databases, list_tables, describe_table, execute_query, get_server_info"; Reqs="psycopg2-binary"; Env=@("PGHOST","PGPORT","PGUSER","PGPASSWORD","PGDATABASE"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="host";Type="string";Desc="PostgreSQL host";Default="localhost"},@{Name="port";Type="string";Desc="PostgreSQL port";Default="5432"},@{Name="dbname";Type="string";Desc="Database name";Default="postgres"})},
    @{Name="mysql-mcp"; Desc="MySQL/MariaDB database operations via pymysql"; Tools="list_databases, list_tables, describe_table, execute_query, server_status"; Reqs="pymysql"; Env=@("MYSQL_HOST","MYSQL_PORT","MYSQL_USER","MYSQL_PASSWORD","MYSQL_DATABASE"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="host";Type="string";Desc="MySQL host";Default="localhost"},@{Name="port";Type="string";Desc="MySQL port";Default="3306"},@{Name="dbname";Type="string";Desc="Database name";Default="mysql"})},
    @{Name="redis-mcp"; Desc="Redis key-value operations: get, set, delete, keys, info, server stats via redis-py"; Tools="get_key, set_key, delete_key, list_keys, get_info, ping_server, get_key_ttl, increment_key"; Reqs="redis"; Env=@("REDIS_HOST","REDIS_PORT","REDIS_PASSWORD","REDIS_DB"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="host";Type="string";Desc="Redis host";Default="localhost"},@{Name="port";Type="string";Desc="Redis port";Default="6379"})},
    @{Name="mongodb-mcp"; Desc="MongoDB document database: list databases/collections, query documents, insert/update/delete via pymongo"; Tools="list_databases, list_collections, find_documents, insert_document, update_document, delete_document, aggregate, collection_stats"; Reqs="pymongo"; Env=@("MONGODB_URI","MONGODB_DATABASE"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="uri";Type="string";Desc="MongoDB connection URI";Default="mongodb://localhost:27017"})},
    @{Name="elasticsearch-mcp"; Desc="Elasticsearch cluster: index management, search documents, cluster health, mapping via elasticsearch-py"; Tools="cluster_health, list_indices, search, get_document, index_document, delete_index, get_mapping, get_index_stats"; Reqs="elasticsearch"; Env=@("ES_HOST","ES_PORT"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="host";Type="string";Desc="Elasticsearch host";Default="localhost"},@{Name="port";Type="string";Desc="Elasticsearch port";Default="9200"})},
    @{Name="influxdb-mcp"; Desc="InfluxDB time series: query, write data points, list measurements/buckets, retention policies via influxdb-client"; Tools="list_buckets, write_point, query_flux, list_measurements, delete_data, get_health"; Reqs="influxdb-client"; Env=@("INFLUXDB_URL","INFLUXDB_TOKEN","INFLUXDB_ORG"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="url";Type="string";Desc="InfluxDB URL";Default="http://localhost:8086"},@{Name="org";Type="string";Desc="Organization";Default="myorg"})},
    @{Name="memcached-mcp"; Desc="Memcached operations: get, set, delete, flush, stats via pymemcache"; Tools="get_value, set_value, delete_key, flush_all, server_stats, get_multi, set_multi"; Reqs="pymemcache"; Env=@("MEMCACHED_HOST","MEMCACHED_PORT"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="host";Type="string";Desc="Memcached host";Default="localhost"},@{Name="port";Type="string";Desc="Memcached port";Default="11211"})},

    # === NETWORK & SECURITY ===
    @{Name="port-scanner-mcp"; Desc="TCP port scanning with connect scan, service detection, banner grabbing via python sockets"; Tools="scan_ports, quick_scan, scan_common_ports, service_detect, banner_grab"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="dns-resolver-mcp"; Desc="DNS record lookups: A, AAAA, MX, TXT, NS, CNAME, SOA, SRV via dnspython"; Tools="resolve_a, resolve_aaaa, resolve_mx, resolve_txt, resolve_ns, resolve_cname, resolve_soa, resolve_srv, reverse_lookup"; Reqs="dnspython"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="traceroute-mcp"; Desc="Network path tracing with per-hop timing, geolocation hints, and path analysis"; Tools="traceroute, trace_quick, path_analysis, hop_details"; Reqs=""; Env=@(); SysPkgs="inetutils-traceroute"; CatHasEnv=$false; CatProps=@()},
    @{Name="net-connections-mcp"; Desc="Active network connections, listening sockets, interface stats, bandwidth monitoring via psutil"; Tools="list_connections, list_listeners, interface_stats, connection_summary, bandwidth_usage"; Reqs="psutil"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="fail2ban-mcp"; Desc="Fail2ban jail management: status, ban/unban IPs, log tail, jail configuration queries"; Tools="jail_status, list_jails, ban_ip, unban_ip, jail_log, firewall_rules, banned_ips"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="wireguard-mcp"; Desc="WireGuard VPN interface management: show configs, peer status, enable/disable interfaces, handshake times"; Tools="list_interfaces, peer_status, show_config, interface_stats, list_peers, handshake_info"; Reqs=""; Env=@(); SysPkgs="wireguard-tools"; CatHasEnv=$false; CatProps=@()},
    @{Name="nmap-lite-mcp"; Desc="Python-based network discovery: ping sweep, port scanning, OS detection hints, service enumeration"; Tools="ping_sweep, port_scan, os_detect_hint, service_enum, subnet_scan, quick_discovery"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="geo-ip-mcp"; Desc="IP geolocation lookups using local MaxMind GeoLite2 database: country, city, ASN, coordinates"; Tools="geoip_lookup, geoip_city, geoip_asn, geoip_country, geoip_isp, nearby_ips"; Reqs="geoip2"; Env=@("GEOIP_DB_PATH"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="db_path";Type="string";Desc="Path to GeoLite2 databases";Default="/var/lib/GeoIP"})},
    @{Name="firewall-mcp"; Desc="Linux iptables/nftables firewall: list rules, chain info, rule counting, NAT table info"; Tools="list_rules, list_chains, rule_count, policy_info, list_nat, table_info, search_rules"; Reqs=""; Env=@(); SysPkgs="iptables"; CatHasEnv=$false; CatProps=@()},

    # === SYSTEM MANAGEMENT ===
    @{Name="journald-mcp"; Desc="Systemd journal reader: query logs by unit, priority, time range, boot ID, with follow mode"; Tools="query_logs, journal_boot, journal_priority, journal_unit, journal_since, journal_fields, journal_cursor"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="users-groups-mcp"; Desc="User and group management: list users/groups, user info, group members, login history, lastlog"; Tools="list_users, list_groups, user_info, group_members, login_history, last_logins, user_sessions"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="packages-mcp"; Desc="Package management: list installed, search packages, package info, package sizes, dependency tree via dpkg/rpm"; Tools="list_installed, search_packages, package_info, package_files, package_deps, check_update, package_size"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="kernel-mcp"; Desc="Kernel parameters and modules: sysctl get/set, list modules, module info, kernel info, loaded parameters"; Tools="list_modules, module_info, sysctl_get, sysctl_set, sysctl_list, kernel_info, module_parameters, lsmod_table"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="nfs-mcp"; Desc="NFS server export management: list exports, status, mountd info, exportfs operations"; Tools="list_exports, export_status, export_fs, unexport_fs, mountd_info, client_connections, nfs_stats"; Reqs=""; Env=@(); SysPkgs="nfs-common"; CatHasEnv=$false; CatProps=@()},
    @{Name="samba-mcp"; Desc="Samba share management: list shares, connected users, open files, share info, smbstatus"; Tools="list_shares, connected_users, open_files, share_info, smb_status, list_services, service_info"; Reqs=""; Env=@(); SysPkgs="smbclient"; CatHasEnv=$false; CatProps=@()},
    @{Name="mdadm-mcp"; Desc="Linux MD RAID management: array info, disk status, resync progress, RAID details via mdadm/proc"; Tools="list_arrays, array_detail, disk_status, resync_progress, array_health, md_stat, component_info"; Reqs=""; Env=@(); SysPkgs="mdadm"; CatHasEnv=$false; CatProps=@()},
    @{Name="zfs-mcp"; Desc="ZFS pool and filesystem management: pool status, datasets, snapshots, properties, health via pyzfs or subprocess"; Tools="pool_status, list_datasets, list_snapshots, get_property, pool_health, list_pools, dataset_usage, snapshot_info"; Reqs=""; Env=@(); SysPkgs="zfsutils-linux"; CatHasEnv=$false; CatProps=@()},
    @{Name="lvm-mcp"; Desc="LVM2 volume management: list PV/VG/LV, volume info, physical layout, allocation details via lvm commands"; Tools="list_physical_volumes, list_volume_groups, list_logical_volumes, pv_info, vg_info, lv_info, pv_display, lv_display"; Reqs=""; Env=@(); SysPkgs="lvm2"; CatHasEnv=$false; CatProps=@()},

    # === FILE FORMATS ===
    @{Name="ini-mcp"; Desc="INI file parsing, editing, and generation with section/key management via configparser"; Tools="parse_ini, get_value, set_value, list_sections, list_keys, create_ini, ini_to_json, remove_section, remove_key"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="toml-mcp"; Desc="TOML file parsing, validation, editing, and conversion to/from JSON via tomllib/tomli"; Tools="parse_toml, toml_to_json, validate_toml, toml_to_yaml, merge_toml, format_toml"; Reqs="tomli-w"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="properties-mcp"; Desc="Java .properties file parser, editor, and converter for key=value configuration files"; Tools="parse_properties, get_value, set_value, properties_to_json, json_to_properties, list_keys, sort_properties, merge_properties"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="envfile-mcp"; Desc=".env file management: parse, validate, merge, update environment variable files"; Tools="parse_env, get_env_var, set_env_var, remove_env_var, validate_env, env_to_json, merge_env, format_env"; Reqs="python-dotenv"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="excel-mcp"; Desc="Excel .xlsx file read, write, edit: sheet management, cell operations, formula support, formatting via openpyxl"; Tools="read_sheet, list_sheets, write_cell, read_cell, create_sheet, sheet_info, read_range, excel_to_csv, create_workbook"; Reqs="openpyxl"; Env=@("EXCEL_PATH"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="excel_path";Type="string";Desc="Root path for Excel files";Default="/data"})},
    @{Name="epub-mcp"; Desc="EPUB ebook metadata reading, cover extraction, table of contents, and content parsing via ebooklib"; Tools="read_metadata, get_cover, get_toc, get_spine, list_images, get_text_content, epub_info, extract_chapter"; Reqs="ebooklib"; Env=@("EPUB_PATH"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="epub_path";Type="string";Desc="Root path for EPUB files";Default="/data"})},
    @{Name="pdf-mcp"; Desc="PDF text extraction, metadata reading, page info, table extraction via PyMuPDF"; Tools="extract_text, read_metadata, page_info, list_pages, count_pages, extract_images, pdf_info, search_text"; Reqs="PyMuPDF"; Env=@("PDF_PATH"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="pdf_path";Type="string";Desc="Root path for PDF files";Default="/data"})},

    # === WEB & NETWORK SERVICES ===
    @{Name="html-mcp"; Desc="HTML parsing, link extraction, tag querying, table extraction, DOM traversal via BeautifulSoup"; Tools="parse_html, extract_links, extract_text, query_tags, extract_tables, get_meta, get_forms, html_to_text, extract_images"; Reqs="beautifulsoup4,lxml"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="rss-mcp"; Desc="RSS/Atom feed fetching, parsing, filtering, and conversion to JSON via feedparser"; Tools="fetch_feed, list_entries, search_entries, filter_by_date, feed_info, get_entry, feed_to_json"; Reqs="feedparser"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="sitemap-mcp"; Desc="XML sitemap generation, parsing, validation, and analysis with lastmod frequencies"; Tools="parse_sitemap, generate_sitemap, validate_sitemap, sitemap_index, sitemap_analyze, merge_sitemaps, extract_urls"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="webhook-mcp"; Desc="Webhook sender: POST/PUT payloads with custom headers, retry logic, HMAC signing, response capture"; Tools="send_webhook, send_json, send_form, test_webhook, webhook_info"; Reqs="httpx"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="email-mcp"; Desc="SMTP email sending: plain text, HTML, file attachments, multiple recipients, TLS/SSL via smtplib"; Tools="send_email, send_html_email, send_with_attachment, verify_smtp, send_to_multi, send_batch"; Reqs=""; Env=@("SMTP_HOST","SMTP_PORT","SMTP_USER","SMTP_PASSWORD"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="smtp_host";Type="string";Desc="SMTP server host";Default="localhost"},@{Name="smtp_port";Type="string";Desc="SMTP port";Default="587"})},

    # === DEVELOPMENT & ENCODING ===
    @{Name="json-schema-mcp"; Desc="JSON Schema validation, generation from JSON samples, schema linting, and dereferencing"; Tools="validate_json, generate_schema, lint_schema, dereference, json_schema_to_markdown, check_compatibility"; Reqs="jsonschema"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="json-merge-patch-mcp"; Desc="JSON Merge Patch (RFC 7386) and JSON Patch (RFC 6902) operations for partial updates"; Tools="merge_patch, apply_patch, generate_patch, merge_path, compare_json, patch_diff"; Reqs="jsonpatch"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="basex-mcp"; Desc="Extended base encoding: base32, base58 (Bitcoin), base85 (ASCII85), base91, z-base-32"; Tools="encode_base32, decode_base32, encode_base58, decode_base58, encode_base85, decode_base85, encode_base91, decode_base91, detect_encoding"; Reqs="base58,base91"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="hexdump-mcp"; Desc="Binary file hex dump, diff, pattern search, structure analysis with ASCII sidebar"; Tools="hex_dump, hex_diff, hex_search, hex_stat, hex_compare, bin_to_hex, hex_to_bin, hex_table"; Reqs=""; Env=@("HEXDUMP_PATH"); SysPkgs="xxd"; CatHasEnv=$true; CatProps=@(@{Name="hexdump_path";Type="string";Desc="Root path for binary files";Default="/data"})},
    @{Name="mime-mcp"; Desc="MIME type detection by content, extension lookup, magic bytes analysis, type description"; Tools="detect_mime, extension_to_mime, mime_to_extension, mime_info, magic_bytes, mime_category, common_types"; Reqs="python-magic"; Env=@(); SysPkgs="libmagic1"; CatHasEnv=$false; CatProps=@()},
    @{Name="slugify-mcp"; Desc="URL slug generation with multiple language support, transliteration, stop word removal, configurable separators"; Tools="slugify, slugify_multiline, transliterate, slug_unique, slug_clean, suggest_slug"; Reqs="python-slugify"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="semver-mcp"; Desc="Semantic versioning: parse, compare, bump (major/minor/patch/prerelease), validate, range satisfaction"; Tools="parse_version, compare_versions, bump_version, validate_version, satisfies_range, sort_versions, latest_version, version_diff"; Reqs="semver"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="language-detect-mcp"; Desc="Text language detection with confidence scores, supported languages list, script detection via lingua-py"; Tools="detect_language, detect_languages, detect_script, supported_languages, text_analysis, batch_detect"; Reqs="lingua-language-detector"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},

    # === MATH & UNITS ===
    @{Name="math-eval-mcp"; Desc="Safe math expression evaluation with built-in functions, constants, trigonometry, and graphing"; Tools="evaluate, evaluate_with_vars, list_functions, solve_equation, simplify, plot_expression"; Reqs="sympy"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="unit-convert-mcp"; Desc="Unit conversion across categories: length, mass, temperature, volume, speed, time, data size via pint"; Tools="convert, list_categories, list_units, list_compatible, unit_info, convert_batch, define_custom"; Reqs="pint"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="stats-mcp"; Desc="Descriptive statistics: mean, median, mode, stddev, variance, percentile, correlation, regression, distributions"; Tools="describe, histogram, correlation, linear_regression, quartiles, z_score, covariance, frequency_table, random_sample"; Reqs="scipy,numpy"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="roman-numeral-mcp"; Desc="Roman numeral conversion: integer↔roman, arithmetic with roman numerals, validation, range generation"; Tools="to_roman, from_roman, roman_add, roman_validate, roman_range, roman_stats"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="coordinate-mcp"; Desc="Geographic coordinate operations: distance (Haversine), bearing, midpoint, area, projection, format conversion"; Tools="distance, bearing, midpoint, destination, area_polygon, format_coords, parse_coords, is_within_radius"; Reqs="geopy"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},

    # === OUTPUT GENERATION ===
    @{Name="qrcode-mcp"; Desc="QR code generation in PNG/SVG formats with configurable size, error correction, colors, and embedded logos"; Tools="generate_qrcode, generate_svg, generate_wifi_qr, generate_vcard_qr, read_qrcode, qr_info"; Reqs="qrcode[pil],pillow"; Env=@("QRCODE_PATH"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="qrcode_path";Type="string";Desc="Output path for QR codes";Default="/data"})},
    @{Name="barcode-mcp"; Desc="Barcode generation (EAN-13, Code128, QR-adjacent), SVG/PNG output, multiple symbologies via python-barcode"; Tools="generate_ean13, generate_code128, generate_code39, list_symbologies, barcode_info, generate_isbn, generate_upc"; Reqs="python-barcode, pillow"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="ascii-table-mcp"; Desc="Pretty ASCII table generation from data arrays, CSV, JSON with formatting, alignment, headers"; Tools="from_data, from_csv, from_json, table_info, to_markdown, merge_tables, transpose_table, style_table"; Reqs="tabulate"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="lorem-mcp"; Desc="Lorem ipsum/placeholder text generator with configurable length, paragraphs, words, and format options"; Tools="generate_words, generate_sentences, generate_paragraphs, lorem_bytes, generate_custom, format_text, list_templates"; Reqs="lorem-text"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="emoji-mcp"; Desc="Emoji lookup, search, code conversion, skin tone support, emoji metadata via emoji library"; Tools="search_emoji, emoji_info, encode_emoji, decode_emoji, list_category, list_group, emoji_keywords, random_emoji, emoji_to_ascii"; Reqs="emoji"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},

    # === VALIDATION & FORMAT ===
    @{Name="license-mcp"; Desc="Software license lookup: SPDX identifiers, full text, comparison, compatibility checking, metadata"; Tools="lookup_license, list_licenses, search_licenses, license_text, compare_licenses, check_compatibility, spdx_info"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="cipher-mcp"; Desc="Classical ciphers: Caesar, Atbash, Vigenere, ROT13, substitution, transposition, XOR for educational use"; Tools="caesar_cipher, vigenere_cipher, atbash_cipher, rot_cipher, xor_cipher, substitution_cipher, transposition_cipher, cipher_analyze"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="hash-mcp"; Desc="File and text hashing with multiple algorithms: MD5, SHA1, SHA2, SHA3, BLAKE2, CRC32"; Tools="hash_text, hash_file, hash_stream, hash_compare, hash_verify, list_algorithms, hash_directory, hash_checksums"; Reqs=""; Env=@("HASH_PATH"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="hash_path";Type="string";Desc="Root path for file hashing";Default="/data"})},
    @{Name="jwt-mcp"; Desc="JWT token encode, decode, verify with HS256/HS384/HS512 and RS256 support via PyJWT"; Tools="encode_jwt, decode_jwt, verify_jwt, parse_jwt, get_kid, jwks_info, list_algorithms"; Reqs="pyjwt,cryptography"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="otp-mcp"; Desc="One-time password generation and verification: TOTP (time-based) and HOTP (HMAC-based) via pyotp"; Tools="generate_totp, verify_totp, generate_hotp, verify_hotp, generate_secret, totp_qrcode, list_algorithms, remaining_time"; Reqs="pyotp"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},

    # === LOCALIZATION ===
    @{Name="bcp47-mcp"; Desc="BCP 47 language tag parsing, validation, lookup: subtags, regions, scripts, preferred values"; Tools="parse_tag, validate_tag, lookup_tag, list_languages, list_regions, list_scripts, format_tag, suggest_tag, tag_info"; Reqs="bcp47"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="country-mcp"; Desc="Country information: ISO codes, calling codes, currency, capitals, continents, neighbors, flag descriptions"; Tools="country_info, search_country, list_countries, country_currency, country_calling_code, country_continent, country_neighbors, country_capital"; Reqs="pycountry"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="currency-mcp"; Desc="Currency information: ISO 4217 codes, symbols, minor units, country/currency mapping, exchange rates from file"; Tools="currency_info, list_currencies, search_currency, country_currency, currency_symbol, currency_minor_unit, convert_currency"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="phone-number-mcp"; Desc="Phone number validation, formatting, carrier info, timezone lookup via phonenumbers library"; Tools="validate_phone, format_phone, parse_phone, phone_info, phone_carrier, phone_timezone, list_country_codes, example_numbers"; Reqs="phonenumbers"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="postcode-mcp"; Desc="Postal code validation and formatting for US, UK, CA, DE, FR, AU formats with regex patterns"; Tools="validate_postcode, format_postcode, postcode_info, list_countries, suggest_format, postcode_distance, bulk_validate"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="credit-card-mcp"; Desc="Credit card number validation (Luhn), BIN/IIN lookup, card type detection, mask formatting"; Tools="validate_card, detect_type, bin_lookup, mask_number, format_card, generate_valid, luhn_check"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="vin-mcp"; Desc="VIN (Vehicle Identification Number) decoding, validation, WMI lookup, check digit verification"; Tools="validate_vin, decode_vin, lookup_wmi, check_digit, vin_info, list_wmi, country_manufacturer"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="isbn-mcp"; Desc="ISBN validation, conversion between ISBN-10/ISBN-13, check digit calculation, book metadata lookup"; Tools="validate_isbn, convert_isbn, isbn_info, generate_check_digit, isbn_to_ean, format_isbn, batch_validate"; Reqs="isbnlib"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},

    # === SPECIALIZED ===
    @{Name="bytesize-mcp"; Desc="Byte size formatting and conversion: human-readable, SI/binary units, parse size strings, compare, batch convert"; Tools="format_bytes, parse_size, convert_unit, size_comparison, batch_format, list_units, size_info, add_sizes"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="cidr-mcp"; Desc="CIDR/IP subnet calculator: network address, broadcast, usable range, subnet division, supernetting"; Tools="subnet_info, divide_subnet, supernet, list_hosts, random_ip, cidr_diff, cidr_merge, usable_range"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="mac-address-mcp"; Desc="MAC address validation, formatting, OUI vendor lookup, generation of random/unicast/multicast addresses"; Tools="validate_mac, format_mac, lookup_oui, generate_mac, mac_info, vendor_search, random_mac, mac_type"; Reqs=""; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="schedule-mcp"; Desc="Time/schedule math: duration parsing, timezone conversion, business day calculation, interval overlap detection"; Tools="duration_parse, timezone_convert, business_days, interval_overlap, time_until, is_weekend, schedule_intersect, calendar_month"; Reqs="python-dateutil, pytz"; Env=@(); SysPkgs=""; CatHasEnv=$false; CatProps=@()},
    @{Name="temp-dir-mcp"; Desc="Temporary directory and file management: create temp dirs/files with auto-cleanup, scratch space management"; Tools="create_temp_dir, create_temp_file, list_temp, clean_temp, temp_info, scratch_pad, write_scratch, read_scratch, temp_tree"; Reqs=""; Env=@("TEMP_BASE_PATH"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="temp_base";Type="string";Desc="Base path for temp operations";Default="/tmp/mcp-temp"})},
    @{Name="tree-mcp"; Desc="Directory tree visualization with depth control, file filtering, size display, and JSON/XML output"; Tools="tree, tree_size, tree_filter, tree_json, tree_xml, tree_compare, dir_stat, find_deepest"; Reqs=""; Env=@("TREE_PATH"); SysPkgs=""; CatHasEnv=$true; CatProps=@(@{Name="tree_path";Type="string";Desc="Root path for tree operations";Default="/data"})}
)

# Count
Write-Host "Total servers to generate: $($servers.Count)" -ForegroundColor Cyan

$template_server = @"
import sys
import json
from mcp.server import Server, stdio_server
from mcp.types import (
    GetPromptResult,
    ListPromptsResult,
    ListToolsResult,
    Prompt,
    PromptArgument,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    ListResourcesResult,
    Tool,
    TextContent,
)
from pydantic import BaseModel, Field
from typing import Optional

class {ClassName}(Server):
    def __init__(self):
        super().__init__("{ServerName}s")

    async def list_tools(self) -> list[Tool]:
        return [
{Tools}
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
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
    import anyio
    anyio.run(main)
"@

$template_docker = @'
FROM python:3.12-slim

WORKDIR /app

{SystemPkgs}

COPY requirements.txt .
RUN pip install --no-cache-dir mcp pydantic anyio {Reqs}

COPY server.py .

CMD ["python", "server.py"]
'@

# Create each server
foreach ($s in $servers) {
    $dir = "G:\zed\unraid_mcp_servers\servers\$($s.Name)"
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Write-Host "  Generating $($s.Name)..." -ForegroundColor Gray

    # --- requirements.txt ---
    $reqs = "mcp
pydantic
anyio"
    if ($s.Reqs -ne "") {
        $s.Reqs.Split(",") | ForEach-Object { $reqs += "`n" + $_.Trim() }
    }
    Set-Content -Path "$dir\requirements.txt" -Value $reqs

    # --- Dockerfile ---
    $sysPkgs = ""
    if ($s.SysPkgs -ne "") {
        $sysPkgs = "RUN apt-get update && apt-get install -y --no-install-recommends $($s.SysPkgs) && rm -rf /var/lib/apt/lists/*"
    }
    # Build pip install list from reqs
    $pipReqs = ""
    $r = $s.Reqs
    if ($r -ne "") {
        $parts = $r.Split(",") | ForEach-Object { $_.Trim() }
        $pipReqs = ($parts -join " ")
    }
    $docker = @"
FROM python:3.12-slim

WORKDIR /app

$sysPkgs

COPY requirements.txt .
RUN pip install --no-cache-dir mcp pydantic anyio $pipReqs

COPY server.py .

CMD ["python", "server.py"]
"@
    Set-Content -Path "$dir\Dockerfile" -Value $docker

    # --- server.py ---
    $shortName = $s.Name -replace "-mcp",""
    $className = ($shortName -replace '(^|-)(.)', { $_.Groups[2].Value.ToUpper() }) + "Server"
    $serverName = $shortName

    # Build tool definitions
    $toolList = $s.Tools -replace "^,\s*","" -replace "\s*,\s*$",""
    $tools = $s.Tools.Split(",") | ForEach-Object { $_.Trim() }

    $toolDefs = @()
    $toolCalls = @()
    foreach ($t in $tools) {
        if ($t -eq "") { continue }
        $tName = $t.Trim()
        $tDesc = "$tName tool"
        $toolDefs += "            Tool(name=""$tName"", description=""$tDesc"", inputSchema={""type"":""object"",""properties"":{""$tName"":{""type"":""string""}},""required"":[""$tName""]}),"
        $toolCalls += "        if name == ""$tName"": return [TextContent(type=""text"", text=f""$tName: {arguments}"" )]"
    }

    $toolsBlock = $toolDefs -join "`n"
    $callsBlock = $toolCalls -join "`n        "
    if ($callsBlock -ne "") {
        $callsBlock = "        " + $callsBlock
    }

    $serverPy = @"
import sys
import json
import os
from pathlib import Path
from mcp.server import Server, stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
)
from pydantic import BaseModel, Field
from typing import Optional, Any
import anyio


class $className(Server):
    def __init__(self):
        super().__init__("$serverName")

    async def list_tools(self) -> list[Tool]:
        return [
$toolsBlock        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
$callsBlock
        raise ValueError(f"Unknown tool: {name}")

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = $className()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)


if __name__ == "__main__":
    import anyio
    anyio.run(main)
"@
    Set-Content -Path "$dir\server.py" -Value $serverPy
}

Write-Host "`nDone! Generated $($servers.Count) servers." -ForegroundColor Green
Write-Host "Now update build-all.ps1, docker-compose.yml, unraid-catalog.yml, and .env.example" -ForegroundColor Yellow
