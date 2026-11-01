#Requires -Version 5.1
<#
.SYNOPSIS  Restore a backup dump. Default target is the scratch database
           `restorecheck` (safe verification). Pass -TargetDb secondvoice for a
           real restore (drops and recreates it — data loss by design).
#>
param(
    [Parameter(Mandatory = $true)][string]$DumpFile,
    [string]$TargetDb = "restorecheck"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $DumpFile)) { throw "dump not found: $DumpFile" }
$full = (Resolve-Path $DumpFile).Path
docker compose exec -T db sh -c "psql -U secondvoice -c 'DROP DATABASE IF EXISTS $TargetDb;' -c 'CREATE DATABASE $TargetDb;'"
if ($LASTEXITCODE -ne 0) { throw "recreate $TargetDb failed" }
docker compose cp $full "db:/tmp/sv-restore.dump"
if ($LASTEXITCODE -ne 0) { throw "upload failed" }
docker compose exec -T db sh -c "pg_restore -U secondvoice -d $TargetDb /tmp/sv-restore.dump"
if ($LASTEXITCODE -ne 0) { throw "pg_restore failed" }
"RESTORE-OK $TargetDb from $DumpFile"
