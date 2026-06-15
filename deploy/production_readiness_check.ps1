param(
  [string]$EnvFile = ".env.production",
  [string]$ComposeFile = "docker-compose.production.yml"
)

$ErrorActionPreference = "Stop"

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
  "HERMES_ORCHESTRATOR_URL=",
  "TELEGRAM_WEBHOOK_URL="
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
  "ALLOWED_ORIGINS=[`"*`"]"
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

if ($composeContent -notmatch "/var/run/docker.sock:/var/run/docker.sock") {
  Fail "Production compose must make the Hermes Docker socket exposure explicit."
}

Write-Host "Production readiness config check passed."
