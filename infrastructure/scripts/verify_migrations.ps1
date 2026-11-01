#Requires -Version 5.1
<#
.SYNOPSIS  Phase 12 migration verification: step every migration down to base on
           a scratch database, upgrade back to head, and prove the chain-built
           schema is byte-identical (modulo comments) to the live database.
#>
$ErrorActionPreference = "Stop"
$scratch = "postgresql+psycopg2://secondvoice:secondvoice@db:5432/migcheck"

function Alembic([string[]]$Extra) {
    $out = docker compose exec -T backend python -m alembic -c alembic.ini -x "url=$scratch" @Extra 2>&1
    if ($LASTEXITCODE -ne 0) { throw "alembic $($Extra -join ' ') failed:`n$out" }
    return ($out -join "").Trim()
}

docker compose exec -T db sh -c "psql -U secondvoice -c 'DROP DATABASE IF EXISTS migcheck;' -c 'CREATE DATABASE migcheck;'" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "scratch db setup failed" }

Alembic @("upgrade", "head") | Out-Null
"upgraded scratch to head"
$steps = 0
while ($steps -lt 20) {
    $cur = Alembic @("current")
    if (-not $cur) { break }
    Alembic @("downgrade", "-1") | Out-Null
    $steps++
    "downgrade step $steps ok (was: $cur)"
}
if (Alembic @("current")) { throw "downgrade did not reach base" }
"reached base after $steps steps"
Alembic @("upgrade", "head") | Out-Null
$scratchHead = Alembic @("current")
$liveHead = ((docker compose exec -T backend python -m alembic -c alembic.ini current 2>&1) -join "").Trim()
"scratch head: $scratchHead"
"live head:    $liveHead"
if ($scratchHead -ne $liveHead) { throw "version pointer mismatch after round-trip" }

docker compose exec -T db sh -c "pg_dump -U secondvoice -s secondvoice > /tmp/schema-live.sql"
docker compose exec -T db sh -c "pg_dump -U secondvoice -s migcheck > /tmp/schema-chk.sql"
if ($LASTEXITCODE -ne 0) { throw "schema dump failed" }
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) "sv-schemas"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
docker compose cp db:/tmp/schema-live.sql "$tmp/schema-live.sql" | Out-Null
docker compose cp db:/tmp/schema-chk.sql "$tmp/schema-chk.sql" | Out-Null
$norm = { param($p) (Get-Content $p) | Where-Object { $_ -notmatch '^\s*--' -and $_ -notmatch '^\s*$' -and $_ -notmatch '^\\' } | Sort-Object }
$diff = Compare-Object (& $norm "$tmp/schema-live.sql") (& $norm "$tmp/schema-chk.sql")
if ($diff) { throw "schema mismatch after round-trip:`n$($diff | Out-String)" }
"MIGRATION-ROUNDTRIP-PASS ($steps downgrades, schema identical)"
