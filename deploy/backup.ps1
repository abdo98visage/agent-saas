param(
  [string]$ComposeFile = "docker-compose.production.yml",
  [string]$EnvFile = ".env.production",
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
  $envValues = @{}
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
      $envValues[$matches[1].Trim()] = $matches[2].Trim().Trim('"')
    }
  }
  $postgresUser = $envValues["POSTGRES_USER"]
  $postgresDb = $envValues["POSTGRES_DB"]
  if (-not $postgresUser -or -not $postgresDb) {
    throw "POSTGRES_USER and POSTGRES_DB must be set in $EnvFile"
  }

  docker compose --env-file $EnvFile -f $ComposeFile exec -T db pg_dump -U $postgresUser $postgresDb | Set-Content -Encoding UTF8 $dbBackup
  docker compose --env-file $EnvFile -f $ComposeFile exec -T hermes-orchestrator tar -C /data/hermes -cf /tmp/hermes-profiles.tar profiles
  $orchestratorContainer = docker compose --env-file $EnvFile -f $ComposeFile ps -q hermes-orchestrator
  docker cp "${orchestratorContainer}:/tmp/hermes-profiles.tar" $hermesBackup
  docker compose --env-file $EnvFile -f $ComposeFile exec -T hermes-orchestrator rm -f /tmp/hermes-profiles.tar
  Write-Output "Database backup: $dbBackup"
  Write-Output "Hermes profile backup: $hermesBackup"
}
finally {
  Pop-Location
}
