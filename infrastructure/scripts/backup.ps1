#Requires -Version 5.1
<#
.SYNOPSIS  Back up the Docker Postgres database (custom format) to backups/.
.NOTES  Binary-safe: pg_dump writes inside the container, then `docker compose cp`
        copies it out (PowerShell `>` redirection would corrupt it as UTF-16).
#>
param([string]$OutDir = "backups")

$ErrorActionPreference = "Stop"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$dest = Join-Path $OutDir "secondvoice-$ts.dump"
docker compose exec -T db sh -c "pg_dump -U secondvoice -Fc secondvoice > /tmp/sv-backup.dump"
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }
docker compose cp db:/tmp/sv-backup.dump $dest
if ($LASTEXITCODE -ne 0) { throw "docker compose cp failed" }
"BACKUP-OK $dest $((Get-Item $dest).Length) bytes"
