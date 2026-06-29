from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_production_compose_has_private_hermes_and_nginx():
    content = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")

    assert "nginx:" in content
    assert "443:443" in content
    assert "HERMES_ORCHESTRATOR_SECRET" in content
    assert "hermes-runtime:" in content
    assert "HERMES_MANAGED_EXTERNALLY: \"true\"" in content
    assert "/var/run/docker.sock:/var/run/docker.sock" not in content
    assert "healthcheck:" in content
    assert "/healthz" in content
    assert "alembic upgrade head" in content
    assert "condition: service_healthy" in content
    assert "NEXT_PUBLIC_API_URL" in content


def test_release_compose_uses_caddy_and_platform_owned_data():
    content = (ROOT / "docker-compose.release.yml").read_text(encoding="utf-8")

    assert "caddy:" in content
    assert "80:80" in content
    assert "443:443" in content
    assert "hermes-runtime:" in content
    assert "HERMES_MANAGED_EXTERNALLY: \"true\"" in content
    assert "${AGENTSAAS_DATA_DIR:-/opt/agentsaas/data}/hermes/profiles:/data/hermes/profiles" in content
    assert "${AGENTSAAS_DATA_DIR:-/opt/agentsaas/data}/postgres:/var/lib/postgresql/data" in content
    assert "/var/run/docker.sock:/var/run/docker.sock" not in content


def test_caddyfile_proxies_api_websocket_and_admin():
    content = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")

    assert "{$DOMAIN}" in content
    assert "path /api/chat/ws/*" in content
    assert "handle /api/*" in content
    assert "reverse_proxy api:8000" in content
    assert "reverse_proxy admin:3000" in content


def test_nginx_proxies_api_and_websocket():
    content = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")

    assert "proxy_set_header Upgrade $http_upgrade" in content
    assert "location /api/chat/ws/" in content
    assert "proxy_pass http://api:8000" in content
    assert "proxy_pass http://admin:3000" in content
    assert "Strict-Transport-Security" in content
    assert "Content-Security-Policy" in content


def test_production_env_example_documents_required_secrets():
    content = (ROOT / ".env.production.example").read_text(encoding="utf-8")

    for name in [
        "SECRET_KEY",
        "FERNET_KEY",
        "POSTGRES_PASSWORD",
        "HERMES_ORCHESTRATOR_SECRET",
        "HERMES_RUN_PATH",
        "HERMES_RUN_STREAM_PATH",
        "ALERT_NOTIFICATION_EMAILS",
        "SMTP_HOST",
    ]:
        assert name in content


def test_backup_restore_and_smoke_scripts_exist():
    for script_name in ["backup.ps1", "restore.ps1", "verify_backup.ps1", "smoke_test.ps1", "production_readiness_check.ps1", "load_test.py"]:
        script = ROOT / "deploy" / script_name
        assert script.exists()
        assert "docker compose" in script.read_text(encoding="utf-8") or script_name in {"verify_backup.ps1", "smoke_test.ps1", "production_readiness_check.ps1", "load_test.py"}


def test_linux_one_command_deployment_scripts_exist():
    for script_name in [
        "install.sh",
        "agentsaas.sh",
        "production_readiness_check.sh",
        "backup.sh",
        "restore.sh",
        "smoke_test.sh",
    ]:
        script = ROOT / "deploy" / script_name
        assert script.exists()
        content = script.read_text(encoding="utf-8")
        assert "#!/usr/bin/env bash" in content

    install = (ROOT / "deploy" / "install.sh").read_text(encoding="utf-8")
    assert "https://get.docker.com" in install
    assert "python -m scripts.bootstrap_production" in install
    assert "wait_for_api_health" in install
    assert "/opt/agentsaas" in install


def test_production_bootstrap_seeds_platform_minimax_key():
    content = (ROOT / "scripts" / "bootstrap_production.py").read_text(encoding="utf-8")

    assert "ADMIN_EMAIL" in content
    assert "ADMIN_PASSWORD" in content
    assert "MINIMAX_API_KEY" in content
    assert 'owner_type="platform"' in content
    assert 'provider="minimax"' in content
    assert "Fernet(settings.fernet_key.encode())" in content


def test_backup_scripts_generate_and_verify_manifest():
    backup = (ROOT / "deploy" / "backup.ps1").read_text(encoding="utf-8")
    restore = (ROOT / "deploy" / "restore.ps1").read_text(encoding="utf-8")
    verify = (ROOT / "deploy" / "verify_backup.ps1").read_text(encoding="utf-8")

    assert "Get-FileHash -Algorithm SHA256" in backup
    assert "Backup manifest" in backup
    assert "Assert-HashMatches" in restore
    assert "ConvertFrom-Json" in verify


def test_frontend_uses_relative_api_by_default():
    client = (ROOT / "frontend" / "src" / "lib" / "api" / "client.ts").read_text(encoding="utf-8")
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")

    assert '|| "/api"' in client
    assert "ARG NEXT_PUBLIC_API_URL=/api" in dockerfile


def test_runtime_security_guards_are_configured():
    config = (ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    websocket = (ROOT / "app" / "api" / "websocket_chat.py").read_text(encoding="utf-8")
    health = (ROOT / "app" / "api" / "health.py").read_text(encoding="utf-8")

    assert "HERMES_ORCHESTRATOR_SECRET must be at least 32 characters" in config
    assert "LLM_PROVIDER must be minimax, openai, or ollama in production" in config
    assert "redis.asyncio" in main
    assert "rate-limit:" in main
    assert "websocket_max_message_bytes" in websocket
    assert '@router.get("/live")' in health
    assert '@router.get("/ready")' in health


def test_telegram_webhook_sends_replies():
    content = (ROOT / "app" / "api" / "telegram.py").read_text(encoding="utf-8")

    assert "sendMessage" in content
    assert "async def _reply" in content
    assert "delivery = await _send_telegram_message" in content


def test_smoke_script_exercises_full_platform_journey():
    content = (ROOT / "deploy" / "smoke_test.ps1").read_text(encoding="utf-8")

    for token in [
        "/api/ready",
        "/api/admin/provider-pricing/",
        "/api/admin/hermes/status",
        "/api/admin/profiles",
        "/api/admin/api-keys",
        "/api/admin/employees",
        "/api/admin/assignments",
        "/api/auth/activate",
        "/api/auth/ws-token",
        "/api/chat/message",
        "/api/admin/sessions/",
        "/api/admin/monitoring/dashboard-stats",
        "/api/admin/usage-report",
        "/api/admin/monitoring/alerts/run",
        "/api/admin/monitoring/alerts",
        "pricing_snapshot",
        "runtime_type = \"hermes\"",
    ]:
        assert token in content


def test_production_readiness_check_covers_new_runtime_guards():
    content = (ROOT / "deploy" / "production_readiness_check.ps1").read_text(encoding="utf-8")

    for token in [
        "WEBSOCKET_MAX_MESSAGE_BYTES",
        "ALERT_NOTIFICATION_EMAILS",
        "SMTP_HOST",
        "HERMES_MANAGED_EXTERNALLY",
        "NEXT_PUBLIC_API_URL",
        "ALLOWED_ORIGINS",
        "HERMES_ORCHESTRATOR_SECRET",
        "docker compose --env-file",
    ]:
        assert token in content


def test_docker_e2e_compose_uses_local_hermes_runtime():
    compose = (ROOT / "docker-compose.e2e.yml").read_text(encoding="utf-8")
    docker_script = (ROOT / "deploy" / "docker_e2e.ps1").read_text(encoding="utf-8")

    assert "hermes-runtime:" in compose
    assert "app.local_hermes_runtime_app:app" in compose
    assert "HERMES_INTERNAL_URL: http://hermes-runtime:8787" in compose
    assert "alembic upgrade head" in compose
    assert "python seed_templates.py" in compose
    assert "smoke_test.ps1" in docker_script


def test_load_test_script_covers_rest_and_websocket_latency():
    content = (ROOT / "deploy" / "load_test.py").read_text(encoding="utf-8")

    for token in [
        "/api/ready",
        "/api/chat/message",
        "/api/auth/ws-token",
        "p95_ms",
        "WebSocket",
        "REST",
    ]:
        assert token in content
