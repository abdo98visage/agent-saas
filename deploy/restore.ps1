param(
  [Parameter(Mandatory = $true)][string]$DatabaseBackup,
  [Parameter(Mandatory = $true)][string]$HermesProfilesBackup,
  [string]$ComposeFile = "docker-compose.production.yml"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$dbBackupPath = Resolve-Path $DatabaseBackup
$profilesBackupPath = Resolve-Path $HermesProfilesBackup

Push-Location $root
try {
  $dbContainer = docker compose -f $ComposeFile ps -q db
  $orchestratorContainer = docker compose -f $ComposeFile ps -q hermes-orchestrator

  docker cp $dbBackupPath "${dbContainer}:/tmp/agentsaas-restore.sql"
  docker compose -f $ComposeFile exec -T db psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -v ON_ERROR_STOP=1 -f /tmp/agentsaas-restore.sql
  docker compose -f $ComposeFile exec -T db rm -f /tmp/agentsaas-restore.sql

  docker cp $profilesBackupPath "${orchestratorContainer}:/tmp/hermes-profiles-restore.tar"
  docker compose -f $ComposeFile exec -T hermes-orchestrator sh -c "rm -rf /data/hermes/profiles && mkdir -p /data/hermes && tar -C /data/hermes -xf /tmp/hermes-profiles-restore.tar"
  docker compose -f $ComposeFile exec -T hermes-orchestrator rm -f /tmp/hermes-profiles-restore.tar
  Write-Output "Restore completed."
}
finally {
  Pop-Location
}
