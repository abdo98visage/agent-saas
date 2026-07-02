param(
  [switch]$Rebuild,
  [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"
$composeFile = "docker-compose.e2e.yml"
$envFile = ".env.docker.local"

$upArgs = @("compose", "--env-file", $envFile, "-f", $composeFile, "up", "-d")
if ($Rebuild) {
  $upArgs += "--build"
}

Write-Output "Starting AgentSaaS Docker E2E stack..."
try {
  docker info | Out-Null
} catch {
  throw "Docker daemon is not available. Start Docker Desktop or the Docker service before running E2E."
}

if ($Rebuild) {
  Write-Output "Resetting E2E containers and volumes..."
  docker compose --env-file $envFile -f $composeFile down -v --remove-orphans
}
docker @upArgs

try {
  Write-Output "Waiting for API health..."
  $healthy = $false
  for ($i = 0; $i -lt 60; $i++) {
    try {
      $status = Invoke-RestMethod -Method GET -Uri "http://localhost:8002/api/status" -TimeoutSec 5
      if ($status.status -eq "healthy") {
        $healthy = $true
        break
      }
    } catch {
      Start-Sleep -Seconds 3
    }
  }
  if (-not $healthy) {
    throw "API did not become healthy on http://localhost:8002"
  }

  .\deploy\smoke_test.ps1 -BaseUrl "http://localhost:8002"
}
finally {
  if (-not $KeepRunning) {
    Write-Output "Stopping AgentSaaS Docker E2E stack..."
    docker compose --env-file $envFile -f $composeFile down --remove-orphans
  } else {
    Write-Output "E2E stack is still running:"
    Write-Output "  API:   http://localhost:8002"
    Write-Output "  Admin: http://localhost:3002"
  }
}
