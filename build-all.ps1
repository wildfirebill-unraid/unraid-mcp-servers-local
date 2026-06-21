$servers = @(
    "filesystem-mcp","system-info-mcp","sqlite-mcp","docker-mcp","check-host-mcp","text-utility-mcp",
    "media-info-mcp","media-convert-mcp","archive-mcp","backup-mcp","process-mcp","log-mcp",
    "yaml-mcp","xml-mcp","diff-mcp","image-mcp","git-mcp","ssl-mcp",
    "service-mcp","cron-mcp","csv-mcp","template-mcp","password-mcp","uuid-mcp",
    "color-mcp","ipcalc-mcp","sort-mcp","finder-mcp","encoding-mcp","markdown-mcp",
    "mempalace-mcp"
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

Write-Host "`nAll 31 builds succeeded!" -ForegroundColor Green
Write-Host "`nImages:" -ForegroundColor Yellow
docker images --filter "reference=unraid-mcp/*" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
