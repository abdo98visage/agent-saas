param(
  [Parameter(Mandatory = $true)][string]$DatabaseBackup,
  [Parameter(Mandatory = $true)][string]$HermesProfilesBackup,
  [string]$ComposeFile = "docker-compose.production.yml",
  [string]$EnvFile = ".env.production"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$dbBackupPath = Resolve-Path $DatabaseBackup
$profilesBackupPath = Resolve-Path $HermesProfilesBackup

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

  $dbContainer = docker compose --env-file $EnvFile -f $ComposeFile ps -q db
  $orchestratorContainer = docker compose --env-file $EnvFile -f $ComposeFile ps -q hermes-orchestrator

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
