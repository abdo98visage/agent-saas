param(
  [string]$ComposeFile = "docker-compose.production.yml",
  [string]$OutputDir = "backups"
)

$ErrorActionPreference = "Stop"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backupRoot = Join-Path $root $OutputDir
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$dbBackup = Join-Path $backupRoot "agentsaas-db-$timestamp.sql"
$hermesBackup = Join-Path $backupRoot "agentsaas-hermes-profiles-$timestamp.tar"

Push-Location $root
try {
  docker compose -f $ComposeFile exec -T db pg_dump -U $env:POSTGRES_USER $env:POSTGRES_DB | Set-Content -Encoding UTF8 $dbBackup
  docker compose -f $ComposeFile exec -T hermes-orchestrator tar -C /data/hermes -cf /tmp/hermes-profiles.tar profiles
  $orchestratorContainer = docker compose -f $ComposeFile ps -q hermes-orchestrator
  docker cp "${orchestratorContainer}:/tmp/hermes-profiles.tar" $hermesBackup
  docker compose -f $ComposeFile exec -T hermes-orchestrator rm -f /tmp/hermes-profiles.tar
  Write-Output "Database backup: $dbBackup"
  Write-Output "Hermes profile backup: $hermesBackup"
}
finally {
  Pop-Location
}
