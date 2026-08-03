param(
  [string]$EnvFile = ".env.production",
  [string]$ComposeFile = "docker-compose.production.yml"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot

if (-not [System.IO.Path]::IsPathRooted($EnvFile)) {
  $EnvFile = Join-Path $repoRoot $EnvFile
}

if (-not [System.IO.Path]::IsPathRooted($ComposeFile)) {
  $ComposeFile = Join-Path $repoRoot $ComposeFile
}

function Fail($Message) {
  Write-Error $Message
  exit 1
}

if (-not (Test-Path $EnvFile)) {
  Fail "Missing $EnvFile. Copy .env.production.example and replace every production value."
}

if (-not (Test-Path $ComposeFile)) {
  Fail "Missing $ComposeFile."
}

$envContent = Get-Content $EnvFile -Raw
$composeContent = Get-Content $ComposeFile -Raw

$requiredKeys = @(
  "ENVIRONMENT=production",
  "DEBUG=False",
  "SECRET_KEY=",
  "FERNET_KEY=",
  "POSTGRES_PASSWORD=",
  "DATABASE_URL=",
  "REDIS_URL=",
  "LLM_PROVIDER=",
  "HERMES_ORCHESTRATOR_SECRET=",
  "HERMES_RUNTIME_SECRET=",
  "METRICS_TOKEN=",
  "HERMES_ORCHESTRATOR_URL=",
  "TELEGRAM_WEBHOOK_URL=",
  "RATE_LIMIT_BACKEND=",
  "WEBSOCKET_MAX_MESSAGE_BYTES=",
  "KPI_TOKEN_ALERT_THRESHOLD=",
  "KPI_COST_ALERT_THRESHOLD=",
  "ALERT_NOTIFICATION_EMAILS=",
  "ALERT_NOTIFICATION_COOLDOWN_MINUTES=",
  "SMTP_HOST=",
  "SMTP_PORT=",
  "SMTP_FROM_EMAIL="
)

foreach ($key in $requiredKeys) {
  if ($envContent -notmatch [regex]::Escape($key)) {
    Fail "Missing required production setting: $key"
  }
}

$forbiddenValues = @(
  "change-me-in-production",
  "replace-with",
  "postgres:postgres",
  "POSTGRES_PASSWORD=postgres",
  "LLM_PROVIDER=mock",
  "ALLOWED_ORIGINS=[`"*`"]",
  "NEXT_PUBLIC_API_URL=http://localhost:8000",
  "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000",
  "HERMES_ORCHESTRATOR_SECRET=replace-with-long-random-shared-secret",
  "SMTP_FROM_EMAIL=alerts@your-domain.example",
  "ALERT_NOTIFICATION_EMAILS=ops@your-domain.example"
)

foreach ($value in $forbiddenValues) {
  if ($envContent.Contains($value)) {
    Fail "Unsafe placeholder/default value found in ${EnvFile}: $value"
  }
}

if ($composeContent -notmatch "alembic upgrade head") {
  Fail "Production compose must run migrations before serving API traffic."
}

if ($composeContent -notmatch "NEXT_PUBLIC_API_URL") {
  Fail "Production compose must pass NEXT_PUBLIC_API_URL to the frontend build."
}

if ($composeContent -match "/var/run/docker.sock:/var/run/docker.sock") {
  Fail "Production compose must not mount the Docker socket for the default platform-owned Hermes runtime."
}

if ($composeContent -notmatch "hermes-runtime:") {
  Fail "Production compose must include a platform-owned hermes-runtime service for Docker validation."
}

if ($composeContent -notmatch "HERMES_MANAGED_EXTERNALLY: `"true`"") {
  Fail "Production compose must explicitly mark the orchestrator as managing the private Hermes runtime."
}

if ($composeContent -notmatch "443:443") {
  Fail "Production compose must expose HTTPS through nginx."
}

if ($composeContent -notmatch "healthcheck:") {
  Fail "Production compose must define health checks for critical services."
}

if ($composeContent -notmatch "condition: service_healthy") {
  Fail "Production compose must gate startup on healthy dependencies."
}

if ($composeContent -notmatch "/healthz" -or $composeContent -notmatch "/health") {
  Fail "Production compose must health check both orchestrator and runtime endpoints."
}

if ($envContent -notmatch "LLM_PROVIDER=(minimax|openai|ollama)") {
  Fail "LLM_PROVIDER must be one of minimax, openai, or ollama in production."
}

$secretMatch = [regex]::Match($envContent, "(?m)^HERMES_ORCHESTRATOR_SECRET=(.+)$")
if (-not $secretMatch.Success -or $secretMatch.Groups[1].Value.Trim().Length -lt 32) {
  Fail "HERMES_ORCHESTRATOR_SECRET must be set to at least 32 characters."
}

$runtimeSecretMatch = [regex]::Match($envContent, "(?m)^HERMES_RUNTIME_SECRET=(.+)$")
if (-not $runtimeSecretMatch.Success -or $runtimeSecretMatch.Groups[1].Value.Trim().Length -lt 32) {
  Fail "HERMES_RUNTIME_SECRET must be set to at least 32 characters."
}

if ($secretMatch.Groups[1].Value.Trim() -eq $runtimeSecretMatch.Groups[1].Value.Trim()) {
  Fail "HERMES_RUNTIME_SECRET must differ from HERMES_ORCHESTRATOR_SECRET."
}

$metricsTokenMatch = [regex]::Match($envContent, "(?m)^METRICS_TOKEN=(.+)$")
if (-not $metricsTokenMatch.Success -or $metricsTokenMatch.Groups[1].Value.Trim().Length -lt 32) {
  Fail "METRICS_TOKEN must be set to at least 32 characters."
}

$allowedOriginsMatch = [regex]::Match($envContent, "(?m)^ALLOWED_ORIGINS=(.+)$")
if (-not $allowedOriginsMatch.Success -or $allowedOriginsMatch.Groups[1].Value -notmatch "https://") {
  Fail "ALLOWED_ORIGINS must use explicit HTTPS origins in production."
}

$apiUrlMatch = [regex]::Match($envContent, "(?m)^NEXT_PUBLIC_API_URL=(.+)$")
if (-not $apiUrlMatch.Success -or $apiUrlMatch.Groups[1].Value.Trim() -notin @("/api")) {
  if ($apiUrlMatch.Groups[1].Value -notmatch "^https://") {
    Fail "NEXT_PUBLIC_API_URL must be `/api` behind nginx or an explicit HTTPS API URL."
  }
}

$smtpHostMatch = [regex]::Match($envContent, "(?m)^SMTP_HOST=(.*)$")
$alertRecipientsMatch = [regex]::Match($envContent, "(?m)^ALERT_NOTIFICATION_EMAILS=(.*)$")
if ($alertRecipientsMatch.Success -and $alertRecipientsMatch.Groups[1].Value.Trim()) {
  if (-not $smtpHostMatch.Success -or -not $smtpHostMatch.Groups[1].Value.Trim()) {
    Fail "SMTP_HOST is required when ALERT_NOTIFICATION_EMAILS is configured."
  }
}

try {
  docker compose --env-file $EnvFile -f $ComposeFile config | Out-Null
} catch {
  Fail "Docker Compose config validation failed with ${EnvFile}: $($_.Exception.Message)"
}

Write-Host "Production readiness config check passed."
Write-Host "Validated env file: $EnvFile"
Write-Host "Validated compose file: $ComposeFile"
