param(
  [string]$BaseUrl = "https://localhost",
  [string]$AdminEmail = "admin@fqsaas.com",
  [string]$AdminPassword = "admin123"
)

$ErrorActionPreference = "Stop"

function Invoke-Json {
  param(
    [string]$Method,
    [string]$Uri,
    [object]$Body = $null,
    [hashtable]$Headers = @{}
  )

  $params = @{
    Method = $Method
    Uri = $Uri
    Headers = $Headers
    ContentType = "application/json"
  }
  if ($null -ne $Body) {
    $params.Body = ($Body | ConvertTo-Json -Depth 20)
  }
  Invoke-RestMethod @params
}

$status = Invoke-Json -Method GET -Uri "$BaseUrl/api/status"
if ($status.status -ne "healthy") {
  throw "API status check failed"
}

$login = Invoke-Json -Method POST -Uri "$BaseUrl/api/auth/login" -Body @{
  email = $AdminEmail
  password = $AdminPassword
}
$headers = @{ Authorization = "Bearer $($login.access_token)" }

$hermes = Invoke-Json -Method GET -Uri "$BaseUrl/api/admin/hermes/status" -Headers $headers
if (-not $hermes.status) {
  throw "Hermes status response is missing status"
}

$profiles = Invoke-Json -Method GET -Uri "$BaseUrl/api/admin/profiles" -Headers $headers
$employees = Invoke-Json -Method GET -Uri "$BaseUrl/api/admin/employees" -Headers $headers
$kpis = Invoke-Json -Method GET -Uri "$BaseUrl/api/admin/kpis" -Headers $headers

Write-Output "Smoke test passed."
Write-Output "Hermes: $($hermes.status)"
Write-Output "Profiles: $($profiles.profiles.Count)"
Write-Output "Employees: $($employees.employees.Count)"
Write-Output "Messages today: $($kpis.summary.messages_today)"
