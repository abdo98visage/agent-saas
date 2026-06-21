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
$manifestPath = Join-Path $backupRoot "agentsaas-backup-$timestamp.manifest.json"

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
  $dbHash = (Get-FileHash -Algorithm SHA256 $dbBackup).Hash
  $hermesHash = (Get-FileHash -Algorithm SHA256 $hermesBackup).Hash
  $manifest = [ordered]@{
    created_at = (Get-Date).ToString("o")
    compose_file = $ComposeFile
    env_file = $EnvFile
    database_backup = @{
      path = (Resolve-Path $dbBackup).Path
      sha256 = $dbHash
    }
    hermes_profiles_backup = @{
      path = (Resolve-Path $hermesBackup).Path
      sha256 = $hermesHash
    }
  }
  $manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $manifestPath
  Write-Output "Database backup: $dbBackup"
  Write-Output "Hermes profile backup: $hermesBackup"
  Write-Output "Backup manifest: $manifestPath"
}
finally {
  Pop-Location
}
