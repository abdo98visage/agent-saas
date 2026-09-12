param(
  [string]$ApiImage = "agentsaas-api:e2e",
  [string]$RuntimeImage = "agentsaas-hermes-runtime:e2e",
  [int]$ApiPort = 8012,
  [int]$RtoTargetSeconds = 300,
  [string]$Evidence = "uat-evidence/phase9-restore-four-users.json"
)

$ErrorActionPreference = "Stop"
$id = [DateTime]::UtcNow.ToString("yyyyMMddHHmmss")
$db = "fqsaas_phase9_$id"
$runtime = "agentsaas-phase9-runtime-$id"
$orchestrator = "agentsaas-phase9-orchestrator-$id"
$api = "agentsaas-phase9-api-$id"
$runtimeNetwork = "agentsaas-phase9-runtime-$id"
$profiles = "agentsaas_phase9_profiles_$id"
$attachments = "agentsaas_phase9_attachments_$id"
$knowledge = "agentsaas_phase9_knowledge_$id"
$dump = "/tmp/phase9-$id.dump"
$started = [DateTime]::UtcNow
$previousKnowledgeRoots = $env:KNOWLEDGE_ALLOWED_ROOTS

function Db([string]$database, [string]$sql) {
  (& docker exec agentsaas-db-1 psql -U postgres -d $database -At -v ON_ERROR_STOP=1 -c $sql).Trim()
}

function Copy-Volume([string]$source, [string]$destination) {
  & docker run --rm -v "${source}:/source:ro" -v "${destination}:/destination" postgres:15-alpine `
    sh -c "cd /source && tar -cf - . | tar -xf - -C /destination"
  if ($LASTEXITCODE -ne 0) { throw "Failed to restore volume $destination" }
}

function Volume-FileCount([string]$volume) {
  return [int]((& docker run --rm -v "${volume}:/data:ro" postgres:15-alpine sh -c "find /data -type f | wc -l").Trim())
}

function Wait-Api {
  $deadline = [DateTime]::UtcNow.AddSeconds(120)
  while ([DateTime]::UtcNow -lt $deadline) {
    try {
      $ready = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/api/ready" -TimeoutSec 5
      if ($ready.status -eq "ready") { return }
    } catch {}
    Start-Sleep -Seconds 2
  }
  throw "Restored API did not become ready"
}

try {
  $countsSql = "select (select count(*) from users),(select count(*) from profiles),(select count(*) from sessions),(select count(*) from messages),(select count(*) from agent_runs),(select count(*) from audit_log),(select count(*) from knowledge_sources),(select count(*) from knowledge_documents),(select count(*) from knowledge_chunks),(select count(*) from mcp_servers),(select count(*) from profile_mcp_bindings);"
  $sourceCounts = Db "fqsaas" $countsSql
  & docker exec agentsaas-db-1 pg_dump -U postgres -d fqsaas -Fc -f $dump
  if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }
  & docker exec agentsaas-db-1 createdb -U postgres $db
  & docker exec agentsaas-db-1 pg_restore -U postgres -d $db --no-owner --no-privileges $dump
  if ($LASTEXITCODE -ne 0) { throw "pg_restore failed" }
  $restoredCounts = Db $db $countsSql
  if ($sourceCounts -ne $restoredCounts) { throw "Restored database counts differ from source" }
  if ((Db $db "select verify_audit_log_chain();") -ne "t") { throw "Restored audit chain is invalid" }

  & docker volume create $profiles | Out-Null
  & docker volume create $attachments | Out-Null
  & docker volume create $knowledge | Out-Null
  Copy-Volume "agentsaas_hermes_profiles" $profiles
  Copy-Volume "agentsaas_attachment_data_e2e" $attachments
  Copy-Volume "agentsaas_knowledge_data_e2e" $knowledge
  $fileCounts = [ordered]@{
    profiles = [ordered]@{ source = (Volume-FileCount "agentsaas_hermes_profiles"); restored = (Volume-FileCount $profiles) }
    attachments = [ordered]@{ source = (Volume-FileCount "agentsaas_attachment_data_e2e"); restored = (Volume-FileCount $attachments) }
    knowledge = [ordered]@{ source = (Volume-FileCount "agentsaas_knowledge_data_e2e"); restored = (Volume-FileCount $knowledge) }
  }
  foreach ($item in $fileCounts.Values) {
    if ($item.source -ne $item.restored) { throw "Restored volume file count differs from source" }
  }
  & docker network create $runtimeNetwork | Out-Null

  $runtimeSecret = "phase9-runtime-secret-$id"
  $orchestratorSecret = "phase9-orchestrator-secret-$id"
  & docker run -d --name $runtime --network $runtimeNetwork --add-host host.docker.internal:host-gateway `
    -e DEFAULT_MODEL=qwen3.6:27b -e HERMES_PROFILES_ROOT=/data/hermes/profiles `
    -e HERMES_RUN_TIMEOUT_SECONDS=120 -e HERMES_RUNTIME_SECRET=$runtimeSecret `
    -e HERMES_RUNTIME_REQUIRE_SECRET=true -v "${profiles}:/data/hermes/profiles:ro" $RuntimeImage `
    uvicorn app.local_hermes_runtime_app:app --host 0.0.0.0 --port 8787 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Restored runtime failed to start" }

  & docker run -d --name $orchestrator --network $runtimeNetwork --add-host host.docker.internal:host-gateway `
    -e HERMES_WORKSPACE_ROOT=/data/hermes/profiles -e HERMES_INTERNAL_URL="http://${runtime}:8787" `
    -e HERMES_RUNTIME_SECRET=$runtimeSecret -e HERMES_ORCHESTRATOR_SECRET=$orchestratorSecret `
    -e HERMES_ORCHESTRATOR_REQUIRE_SECRET=true `
    -e HERMES_MODEL_PROXY_URL="http://${orchestrator}:8788/internal/model/v1/chat/completions" `
    -e OPENAI_BASE_URL=http://host.docker.internal:60000/v1/chat/completions `
    -e MINIMAX_BASE_URL=https://api.minimax.io/v1/chat/completions `
    -e HERMES_MANAGED_EXTERNALLY=true -e HERMES_RUN_PATH=/runs -e HERMES_RUN_STREAM_PATH=/runs/stream `
    -e HERMES_HEALTH_PATH=/health -v "${profiles}:/data/hermes/profiles" $ApiImage `
    uvicorn app.hermes_orchestrator_app:app --host 0.0.0.0 --port 8788 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Restored orchestrator failed to start" }
  & docker network connect agentsaas_app_net $orchestrator

  $env:KNOWLEDGE_ALLOWED_ROOTS = '["/data/knowledge"]'
  & docker run -d --name $api --network agentsaas_app_net -p "${ApiPort}:8000" --env-file .env.docker.local `
    -e "DATABASE_URL=postgresql+asyncpg://postgres:postgres@agentsaas-db-1:5432/$db" `
    -e REDIS_URL=redis://agentsaas-redis-1:6379/0 `
    -e "HERMES_ORCHESTRATOR_URL=http://${orchestrator}:8788" -e HERMES_ORCHESTRATOR_SECRET=$orchestratorSecret `
    -e ATTACHMENT_STORAGE_ROOT=/data/attachments -e KNOWLEDGE_ALLOWED_ROOTS `
    -v "${attachments}:/data/attachments" -v "${knowledge}:/data/knowledge:ro" $ApiImage `
    uvicorn app.main:app --host 0.0.0.0 --port 8000 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Restored API failed to start" }
  Wait-Api
  $rto = [int]([DateTime]::UtcNow - $started).TotalSeconds
  if ($rto -gt $RtoTargetSeconds) { throw "RTO exceeded: $rto > $RtoTargetSeconds" }

  $rows = Db $db @"
select distinct on (u.id) u.email,p.name,s.id,
  (regexp_match(m.content,'CAP-[0-9]+-[0-9]+-[0-9]+'))[1]
from users u
join profile_users pu on pu.user_id=u.id
join profiles p on p.id=pu.profile_id
join sessions s on s.user_id=u.id
join messages m on m.session_id=s.id and m.role='user'
where u.id in (
 '2aad0a66-39f2-4563-9388-d3f3b94cafff','fbcea19c-fb81-4002-a75d-86fdb4ff1f0b',
 'f8f6866d-bdf4-4a05-9e8a-46bf7e963a60','deb69482-3e07-4ec6-af14-9200edf6ea81'
) and m.content ~ 'CAP-[0-9]+-[0-9]+-[0-9]+'
order by u.id,m.created_at desc;
"@
  $results = @()
  foreach ($line in ($rows -split "`n")) {
    $parts = $line.Trim() -split '\|', 4
    if ($parts.Count -ne 4) { continue }
    $loginBody = @{ email = $parts[0]; password = "Employee123" } | ConvertTo-Json
    $login = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$ApiPort/api/auth/login" -ContentType "application/json" -Body $loginBody -TimeoutSec 30
    $headers = @{ Authorization = "Bearer $($login.access_token)" }
    $body = @{
      message = "What exact CAP marker did I ask you to use in the previous turn? Reply with only that marker."
      conversation_id = $parts[2]
      profile_name = $parts[1]
      agent_template_name = "default"
    } | ConvertTo-Json
    $reply = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$ApiPort/api/chat/message" -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec 180
    if ($reply.content -notlike "*$($parts[3])*" ) { throw "Restored conversation continuity failed for $($parts[0])" }
    $results += [ordered]@{ email = $parts[0]; conversation_id = $parts[2]; marker = $parts[3]; status = "passed" }
  }
  if ($results.Count -ne 4) { throw "Expected four restored user conversations, got $($results.Count)" }
  if ((Db $db "select verify_audit_log_chain();") -ne "t") { throw "Audit chain failed after restored user traffic" }

  $summary = [ordered]@{
    status = "passed"
    restored_api = "http://127.0.0.1:$ApiPort"
    source_counts = $sourceCounts
    restored_counts = $restoredCounts
    audit_chain_valid = $true
    measured_rto_seconds = $rto
    rto_target_seconds = $RtoTargetSeconds
    volume_file_counts = $fileCounts
    users = $results
  }
  $evidencePath = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path $Evidence
  New-Item -ItemType Directory -Force -Path (Split-Path $evidencePath -Parent) | Out-Null
  $summary | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $evidencePath
  $summary | ConvertTo-Json -Depth 6 -Compress
}
finally {
  if ($null -eq $previousKnowledgeRoots) { Remove-Item Env:KNOWLEDGE_ALLOWED_ROOTS -ErrorAction SilentlyContinue }
  else { $env:KNOWLEDGE_ALLOWED_ROOTS = $previousKnowledgeRoots }
  foreach ($container in @($api, $orchestrator, $runtime)) {
    if (& docker ps -a -q -f "name=^/${container}$") { & docker rm -f $container | Out-Null }
  }
  if (& docker network ls -q -f "name=^${runtimeNetwork}$") { & docker network rm $runtimeNetwork | Out-Null }
  foreach ($volume in @($profiles, $attachments, $knowledge)) {
    if (& docker volume ls -q -f "name=^${volume}$") { & docker volume rm $volume | Out-Null }
  }
  try { & docker exec agentsaas-db-1 dropdb -U postgres --if-exists --force $db | Out-Null } catch {}
  try { & docker exec agentsaas-db-1 rm -f $dump | Out-Null } catch {}
}
