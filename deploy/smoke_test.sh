#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${AGENTSAAS_HOME:-/opt/agentsaas}"
ENV_FILE="${ENV_FILE:-$APP_HOME/.env.production}"
BASE_URL="${BASE_URL:-}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

get_env() {
  grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2-
}

if [[ -z "$BASE_URL" ]]; then
  BASE_URL="https://$(get_env DOMAIN)"
fi
if [[ -z "$ADMIN_EMAIL" ]]; then
  ADMIN_EMAIL="$(get_env ADMIN_EMAIL)"
fi
if [[ -z "$ADMIN_PASSWORD" ]]; then
  ADMIN_PASSWORD="$(get_env ADMIN_PASSWORD)"
fi

json() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local auth="${4:-}"
  local args=(-fsS -X "$method" "$BASE_URL$path" -H "Content-Type: application/json")
  if [[ -n "$auth" ]]; then
    args+=(-H "Authorization: Bearer $auth")
  fi
  if [[ -n "$body" ]]; then
    args+=(-d "$body")
  fi
  curl "${args[@]}"
}

suffix="$(openssl rand -hex 4)"
profile_name="Smoke Marketing $suffix"
profile_slug="smoke-marketing-$suffix"
employee_email="smoke-$suffix@example.com"

echo "Checking health..."
json GET /api/status | jq -e '.status == "healthy"' >/dev/null
json GET /api/ready | jq -e '.status == "ready"' >/dev/null

echo "Logging in..."
login="$(json POST /api/auth/login "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")"
admin_token="$(echo "$login" | jq -r '.access_token')"
[[ -n "$admin_token" && "$admin_token" != "null" ]]

echo "Checking Hermes..."
json GET /api/admin/hermes/status "" "$admin_token" | jq -e '.status' >/dev/null

echo "Configuring MiniMax pricing..."
json PUT /api/admin/provider-pricing/minimax '{"currency":"USD","monthly_price_usd":20,"monthly_token_allowance":1700000000}' "$admin_token" | jq -e '.provider == "minimax"' >/dev/null

echo "Creating Hermes profile..."
profile_payload="$(jq -n \
  --arg name "$profile_name" \
  --arg slug "$profile_slug" \
  '{name:$name, slug:$slug, runtime_type:"hermes", agents_md:"# Smoke Agent\nHandle smoke validation.", soul_md:"Pragmatic smoke-test operator.", skills:["campaigns","copywriting"], system_prompt:"Answer concisely for smoke validation.", max_tokens_per_day:100000, max_requests_per_day:1000, daily_cost_budget:100000, allowed_providers:["minimax"], allowed_tools:["local_runtime"], allowed_mcp_servers:[] }')"
profile="$(json POST /api/admin/profiles "$profile_payload" "$admin_token")"
echo "$profile" | jq -e '.hermes_sync_status == "synced"' >/dev/null

echo "Creating employee..."
employee_payload="$(jq -n --arg email "$employee_email" '{email:$email, full_name:"Smoke Employee", department:"marketing", role:"employee", max_tokens_per_day:100000, max_requests_per_day:1000}')"
employee="$(json POST /api/admin/employees "$employee_payload" "$admin_token")"
employee_id="$(echo "$employee" | jq -r '.id')"
invite_token="$(echo "$employee" | jq -r '.invite_token')"

profile_id="$(json GET /api/admin/profiles "" "$admin_token" | jq -r --arg slug "$profile_slug" '.profiles[] | select(.slug == $slug) | .id')"

echo "Assigning profile..."
assignment_payload="$(jq -n --arg user_id "$employee_id" --arg profile_id "$profile_id" '{user_id:$user_id, profile_id:$profile_id, priority:0}')"
json POST /api/admin/assignments "$assignment_payload" "$admin_token" | jq -e '.id' >/dev/null

echo "Activating employee..."
activation_payload="$(jq -n --arg token "$invite_token" '{token:$token, password:"Employee123"}')"
activation="$(json POST /api/auth/activate "$activation_payload")"
employee_token="$(echo "$activation" | jq -r '.access_token')"

echo "Sending Hermes chat message..."
chat_payload="$(jq -n --arg profile "$profile_name" '{message:"Write one short smoke-test headline.", profile_name:$profile, agent_template_name:"default", project_context:"Smoke validation."}')"
chat="$(json POST /api/chat/message "$chat_payload" "$employee_token")"
echo "$chat" | jq -e '.conversation_id and .content' >/dev/null

echo "Checking reporting..."
json GET /api/admin/monitoring/dashboard-stats "" "$admin_token" | jq -e '.summary' >/dev/null
json GET /api/admin/usage-report "" "$admin_token" | jq -e '.summary' >/dev/null
json POST /api/admin/monitoring/alerts/run '{}' "$admin_token" | jq -e '.generated != null' >/dev/null

echo "Smoke journey passed."
