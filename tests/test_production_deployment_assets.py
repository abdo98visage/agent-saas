from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_production_compose_has_private_hermes_and_nginx():
    content = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")

    assert "nginx:" in content
    assert "443:443" in content
    assert "HERMES_ORCHESTRATOR_SECRET" in content
    assert "HERMES_PUBLISH_PORT: \"false\"" in content
    assert "AGENTSAAS_DOCKER_NETWORK" in content
    assert "/var/run/docker.sock:/var/run/docker.sock" in content
    assert "healthcheck:" in content
    assert "/healthz" in content


def test_nginx_proxies_api_and_websocket():
    content = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")

    assert "proxy_set_header Upgrade $http_upgrade" in content
    assert "location /api/chat/ws/" in content
    assert "proxy_pass http://api:8000" in content
    assert "proxy_pass http://admin:3000" in content


def test_production_env_example_documents_required_secrets():
    content = (ROOT / ".env.production.example").read_text(encoding="utf-8")

    for name in [
        "SECRET_KEY",
        "FERNET_KEY",
        "POSTGRES_PASSWORD",
        "HERMES_ORCHESTRATOR_SECRET",
        "HERMES_RUN_PATH",
        "HERMES_RUN_STREAM_PATH",
    ]:
        assert name in content


def test_backup_restore_and_smoke_scripts_exist():
    for script_name in ["backup.ps1", "restore.ps1", "smoke_test.ps1"]:
        script = ROOT / "deploy" / script_name
        assert script.exists()
        assert "docker compose" in script.read_text(encoding="utf-8") or script_name == "smoke_test.ps1"
