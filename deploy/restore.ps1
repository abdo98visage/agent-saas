param(
  [Parameter(Mandatory = $true)][string]$DatabaseBackup,
  [Parameter(Mandatory = $true)][string]$HermesProfilesBackup,
  [string]$ManifestPath = "",
  [string]$ComposeFile = "docker-compose.production.yml",
  [string]$EnvFile = ".env.production"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$dbBackupPath = Resolve-Path $DatabaseBackup
$profilesBackupPath = Resolve-Path $HermesProfilesBackup

function Assert-HashMatches($Path, $ExpectedHash) {
  $actualHash = (Get-FileHash -Algorithm SHA256 $Path).Hash
  if ($actualHash -ne $ExpectedHash) {
    throw "Backup hash mismatch for $Path"
  }
}

Push-Location $root
try {
  if (-not $ManifestPath) {
    $candidate = [System.IO.Path]::ChangeExtension($dbBackupPath.Path, ".manifest.json")
    if (Test-Path $candidate) {
      $ManifestPath = $candidate
    }
  }

  if ($ManifestPath) {
    $resolvedManifest = Resolve-Path $ManifestPath
    $manifest = Get-Content $resolvedManifest -Raw | ConvertFrom-Json
    Assert-HashMatches $dbBackupPath $manifest.database_backup.sha256
    Assert-HashMatches $profilesBackupPath $manifest.hermes_profiles_backup.sha256
  }

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

  $dbContainer = docker compose --env-file $EnvFile -f $ComposeFile ps -q db
  $orchestratorContainer = docker compose --env-file $EnvFile -f $ComposeFile ps -q hermes-orchestrator
  if (-not $dbContainer -or -not $orchestratorContainer) {
    throw "Production containers are not running. Start the stack before restore."
  }

  docker cp $dbBackupPath "${dbContainer}:/tmp/agentsaas-restore.sql"
  docker compose --env-file $EnvFile -f $ComposeFile exec -T db psql -U $postgresUser -d $postgresDb -v ON_ERROR_STOP=1 -f /tmp/agentsaas-restore.sql
  docker compose --env-file $EnvFile -f $ComposeFile exec -T db rm -f /tmp/agentsaas-restore.sql

  docker cp $profilesBackupPath "${orchestratorContainer}:/tmp/hermes-profiles-restore.tar"
  docker compose --env-file $EnvFile -f $ComposeFile exec -T hermes-orchestrator sh -c "rm -rf /data/hermes/profiles && mkdir -p /data/hermes && tar -C /data/hermes -xf /tmp/hermes-profiles-restore.tar"
  docker compose --env-file $EnvFile -f $ComposeFile exec -T hermes-orchestrator rm -f /tmp/hermes-profiles-restore.tar
  Write-Output "Restore completed."
}
finally {
  Pop-Location
}
