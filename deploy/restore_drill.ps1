param(
  [string]$ComposeFile = "docker-compose.e2e.yml",
  [string]$EnvFile = ".env.docker.local",
  [int]$RtoTargetSeconds = 300
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$id = [DateTime]::UtcNow.ToString("yyyyMMddHHmmss")
$work = Join-Path $root ".tmp-restore-drill-$id"
$started = [DateTime]::UtcNow
New-Item -ItemType Directory -Force -Path $work | Out-Null

function Compose { & docker compose --env-file $EnvFile -f $ComposeFile @args }

try {
  $dbContainer = (Compose ps -q db).Trim()
  $orchestratorContainer = (Compose ps -q hermes-orchestrator).Trim()
  if (-not $dbContainer -or -not $orchestratorContainer) { throw "Required live containers are missing" }
  $envValues = @{}
  Get-Content (Join-Path $root $EnvFile) | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') { $envValues[$matches[1].Trim()] = $matches[2].Trim().Trim('"') }
  }
  $dbUser = $envValues.POSTGRES_USER; $dbName = $envValues.POSTGRES_DB
  if ($dbName -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') { throw "Unsafe database name" }
  $tempDb = "${dbName}_drill_$id"
  $dumpInContainer = "/tmp/agentsaas-drill-$id.dump"
  $dumpOnHost = Join-Path $work "postgres.dump"
  $profilesOnHost = Join-Path $work "profiles.tar"

  Compose exec -T db pg_dump -U $dbUser -d $dbName -Fc -f $dumpInContainer
  docker cp "${dbContainer}:$dumpInContainer" $dumpOnHost
  Compose exec -T db rm -f $dumpInContainer
  Compose exec -T hermes-orchestrator tar -C /data/hermes -cf "/tmp/profiles-$id.tar" profiles
  docker cp "${orchestratorContainer}:/tmp/profiles-$id.tar" $profilesOnHost
  Compose exec -T hermes-orchestrator rm -f "/tmp/profiles-$id.tar"

  $sourceCounts = (Compose exec -T db psql -U $dbUser -d $dbName -At -c "select (select count(*) from users),(select count(*) from profiles),(select count(*) from messages),(select count(*) from audit_log),(select count(*) from knowledge_sources),(select count(*) from knowledge_documents),(select count(*) from knowledge_chunks);").Trim()
  Compose exec -T db createdb -U $dbUser $tempDb
  docker cp $dumpOnHost "${dbContainer}:/tmp/restore-drill.dump"
  Compose exec -T db pg_restore -U $dbUser -d $tempDb --no-owner --no-privileges "/tmp/restore-drill.dump"
  $restoredCounts = (Compose exec -T db psql -U $dbUser -d $tempDb -At -c "select (select count(*) from users),(select count(*) from profiles),(select count(*) from messages),(select count(*) from audit_log),(select count(*) from knowledge_sources),(select count(*) from knowledge_documents),(select count(*) from knowledge_chunks);").Trim()
  $schema = (Compose exec -T db psql -U $dbUser -d $tempDb -At -c "select version_num from alembic_version;").Trim()
  $auditValid = (Compose exec -T db psql -U $dbUser -d $tempDb -At -c "select verify_audit_log_chain();").Trim()
  tar -tf $profilesOnHost | Out-Null
  if ($sourceCounts -ne $restoredCounts -or $auditValid -ne "t") { throw "Restored database validation failed" }
  $rto = [int]([DateTime]::UtcNow - $started).TotalSeconds
  if ($rto -gt $RtoTargetSeconds) { throw "Restore drill exceeded RTO target: ${rto}s > ${RtoTargetSeconds}s" }
  [pscustomobject]@{
    status = "passed"; schema = $schema; source_counts = $sourceCounts; restored_counts = $restoredCounts
    audit_chain_valid = $true; snapshot_window_seconds = $rto; measured_rto_seconds = $rto; rto_target_seconds = $RtoTargetSeconds
  } | ConvertTo-Json -Compress
}
finally {
  if ($tempDb) { Compose exec -T db dropdb -U $dbUser --if-exists $tempDb | Out-Null }
  if ($dbContainer) { Compose exec -T db rm -f "/tmp/restore-drill.dump" | Out-Null }
  $resolvedWork = [System.IO.Path]::GetFullPath($work)
  if ($resolvedWork.StartsWith($root + [System.IO.Path]::DirectorySeparatorChar) -and (Split-Path $resolvedWork -Leaf).StartsWith(".tmp-restore-drill-")) {
    Remove-Item -LiteralPath $resolvedWork -Recurse -Force -ErrorAction SilentlyContinue
  }
}
