param(
  [string]$BaseUrl = "http://localhost:8002",
  [string]$AdminEmail = "admin@company.com",
  [string]$AdminPassword = "admin123",
  [string]$EmployeePassword = "Employee123",
  [string]$Provider = "minimax",
  [string]$DummyProviderKey = "sk-e2e-dummy-provider-key"
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
    $params.Body = ($Body | ConvertTo-Json -Depth 30)
  }
  Invoke-RestMethod @params
}

function Assert-Truthy {
  param([object]$Value, [string]$Message)
  if (-not $Value) {
    throw $Message
  }
}

$suffix = ([guid]::NewGuid().ToString("N")).Substring(0, 8)
$profileName = "E2E Marketing $suffix"
$profileSlug = "e2e-marketing-$suffix"
$employeeEmail = "e2e-$suffix@example.com"

Write-Output "Checking API health at $BaseUrl ..."
$status = Invoke-Json -Method GET -Uri "$BaseUrl/api/status"
if ($status.status -ne "healthy") {
  throw "API status check failed"
}
$ready = Invoke-Json -Method GET -Uri "$BaseUrl/api/ready"
if ($ready.status -ne "ready") {
  throw "API readiness check failed"
}

Write-Output "Logging in as admin $AdminEmail ..."
$login = Invoke-Json -Method POST -Uri "$BaseUrl/api/auth/login" -Body @{
  email = $AdminEmail
  password = $AdminPassword
}
$adminHeaders = @{ Authorization = "Bearer $($login.access_token)" }

Write-Output "Configuring provider pricing for $Provider ..."
$pricing = Invoke-Json -Method PUT -Uri "$BaseUrl/api/admin/provider-pricing/$Provider" -Headers $adminHeaders -Body @{
  currency = "USD"
  monthly_price_usd = 20
  monthly_token_allowance = 1700000000
}
Assert-Truthy $pricing.provider "Provider pricing did not return provider"

Write-Output "Checking Hermes runtime status ..."
$hermes = Invoke-Json -Method GET -Uri "$BaseUrl/api/admin/hermes/status" -Headers $adminHeaders
Assert-Truthy $hermes.status "Hermes status response is missing status"

Write-Output "Creating Hermes profile $profileSlug ..."
$profile = Invoke-Json -Method POST -Uri "$BaseUrl/api/admin/profiles" -Headers $adminHeaders -Body @{
  name = $profileName
  slug = $profileSlug
  runtime_type = "hermes"
  agents_md = "# E2E Marketing Agent`nHandle marketing requests."
  soul_md = "Pragmatic marketing operator."
  skills = @("campaigns", "copywriting")
  system_prompt = "Answer concisely for E2E validation."
  max_tokens_per_day = 100000
  max_requests_per_day = 1000
  daily_cost_budget = 100000
  allowed_providers = @($Provider)
  allowed_tools = @("local_runtime")
  allowed_mcp_servers = @()
}
Assert-Truthy $profile.id "Profile creation did not return id"
if ($profile.hermes_sync_status -ne "synced") {
  throw "Profile did not sync to Hermes. Status: $($profile.hermes_sync_status), Error: $($profile.hermes_sync_error)"
}

Write-Output "Creating profile-level API key ..."
$apiKey = Invoke-Json -Method POST -Uri "$BaseUrl/api/admin/api-keys" -Headers $adminHeaders -Body @{
  owner_type = "profile"
  profile_id = $profile.id
  provider = $Provider
  api_key = $DummyProviderKey
  daily_budget = 100000
}
Assert-Truthy $apiKey.id "API key creation did not return id"

Write-Output "Creating employee $employeeEmail ..."
$employee = Invoke-Json -Method POST -Uri "$BaseUrl/api/admin/employees" -Headers $adminHeaders -Body @{
  email = $employeeEmail
  full_name = "E2E Employee"
  department = "marketing"
  role = "employee"
  max_tokens_per_day = 100000
  max_requests_per_day = 1000
}
Assert-Truthy $employee.id "Employee creation did not return id"
Assert-Truthy $employee.invite_token "Employee creation did not return invite token"

Write-Output "Assigning profile to employee ..."
$assignment = Invoke-Json -Method POST -Uri "$BaseUrl/api/admin/assignments" -Headers $adminHeaders -Body @{
  user_id = $employee.id
  profile_id = $profile.id
  priority = 0
}
Assert-Truthy $assignment.id "Assignment creation did not return id"

Write-Output "Activating employee ..."
$activation = Invoke-Json -Method POST -Uri "$BaseUrl/api/auth/activate" -Body @{
  token = $employee.invite_token
  password = $EmployeePassword
}
$employeeHeaders = @{ Authorization = "Bearer $($activation.access_token)" }

Write-Output "Sending employee chat message through Hermes profile ..."
$chat = Invoke-Json -Method POST -Uri "$BaseUrl/api/chat/message" -Headers $employeeHeaders -Body @{
  message = "Write one short campaign headline for the E2E test."
  profile_name = $profileName
  agent_template_name = "default"
  project_context = "E2E project context: smoke validation."
}
Assert-Truthy $chat.conversation_id "Chat did not return conversation_id"
Assert-Truthy $chat.content "Chat did not return content"

Write-Output "Requesting one-time WebSocket ticket ..."
$wsToken = Invoke-Json -Method POST -Uri "$BaseUrl/api/auth/ws-token" -Headers $employeeHeaders
Assert-Truthy $wsToken.access_token "WebSocket token did not return access token"

Write-Output "Checking admin session details and run events ..."
$session = Invoke-Json -Method GET -Uri "$BaseUrl/api/admin/sessions/$($chat.conversation_id)" -Headers $adminHeaders
if ($session.messages.Count -lt 2) {
  throw "Session does not contain both user and assistant messages"
}
if ($session.runs.Count -lt 1) {
  throw "Session does not contain agent run records"
}
if ($session.runs[0].runtime_type -ne "hermes") {
  throw "Expected Hermes runtime, got $($session.runs[0].runtime_type)"
}
if (-not $session.runs[0].pricing_snapshot) {
  throw "Run does not contain pricing_snapshot"
}
if ([int]$session.runs[0].total_tokens -lt 1) {
  throw "Run total_tokens was not recorded"
}

Write-Output "Checking KPIs and dashboard observability ..."
$kpis = Invoke-Json -Method GET -Uri "$BaseUrl/api/admin/kpis" -Headers $adminHeaders
$dashboard = Invoke-Json -Method GET -Uri "$BaseUrl/api/admin/monitoring/dashboard-stats" -Headers $adminHeaders
Assert-Truthy $dashboard.summary "Dashboard stats response is missing summary"
if ([int]$dashboard.summary.messages_today -lt 1) {
  throw "Dashboard messages_today did not update"
}
if ([int]$dashboard.summary.tokens_today -lt 1) {
  throw "Dashboard tokens_today did not update"
}
if ($dashboard.profile_usage.Count -lt 1) {
  throw "Dashboard profile_usage is empty"
}

Write-Output "Checking usage reporting and alerting ..."
$usage = Invoke-Json -Method GET -Uri "$BaseUrl/api/admin/usage-report" -Headers $adminHeaders
if ([int]$usage.summary.total_tokens -lt 1) {
  throw "Usage report total_tokens did not update"
}
if ([double]$usage.summary.total_cost -lt 0) {
  throw "Usage report total_cost is invalid"
}
if (-not $usage.pricing -or $usage.pricing.provider -ne $Provider) {
  throw "Usage report pricing does not reflect active provider pricing"
}

$alertRun = Invoke-Json -Method POST -Uri "$BaseUrl/api/admin/monitoring/alerts/run" -Headers $adminHeaders
if ($null -eq $alertRun.generated) {
  throw "Alert evaluation response is missing generated count"
}
$alerts = Invoke-Json -Method GET -Uri "$BaseUrl/api/admin/monitoring/alerts" -Headers $adminHeaders
if ($null -eq $alerts.items) {
  throw "Alerts list did not return items"
}

Write-Output "Smoke journey passed."
Write-Output "Hermes status: $($hermes.status)"
Write-Output "Profile: $profileSlug"
Write-Output "Employee: $employeeEmail"
Write-Output "Conversation: $($chat.conversation_id)"
Write-Output "KPIs returned: $($kpis.count)"
Write-Output "Usage total tokens: $($usage.summary.total_tokens)"
Write-Output "Alerts count: $($alerts.count)"
