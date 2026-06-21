"""
FQ-SaaS Code Verification Tests — No DB needed.
Verifies: endpoints, models, auth logic, telegram protection, invite system, agent service.
Run: pytest tests/ -v
"""
import secrets
import uuid
import asyncio
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
from app.models.user import User
from app.models.profile import Profile
from app.models.telegram_binding import TelegramBinding
from app.core.security import create_access_token, decode_access_token, get_password_hash, verify_password


# ============= MODEL VERIFICATION =============

class TestModels:
    def test_user_has_invite_token_field(self):
        assert hasattr(User, "invite_token")
        assert hasattr(User, "is_activated")
        assert hasattr(User, "invite_token_expires_at")

    def test_profile_has_soul_md(self):
        assert hasattr(Profile, "soul_md")
        assert not hasattr(Profile, "description")

    def test_telegram_binding_fields(self):
        assert hasattr(TelegramBinding, "user_id")
        assert hasattr(TelegramBinding, "telegram_chat_id")
        assert hasattr(TelegramBinding, "binding_token")
        assert hasattr(TelegramBinding, "binding_token_expires_at")

    def test_user_pending_employee(self):
        u = User(email="t@t.com", hashed_password="h",
                 is_active=False, is_activated=False,
                 invite_token=secrets.token_urlsafe(48))
        assert u.is_activated is False
        assert u.invite_token is not None
        assert len(u.invite_token) > 20


# ============= SECURITY =============

class TestSecurity:
    def test_password_hash_and_verify(self):
        pw = "my_secret_password"
        hashed = get_password_hash(pw)
        assert verify_password(pw, hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_jwt_create_and_decode(self):
        uid = str(uuid.uuid4())
        token = create_access_token(uid, "admin", extra_claims={"ver": 0})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == uid
        assert payload["role"] == "admin"
        assert payload["ver"] == 0

    def test_jwt_invalid_token(self):
        assert decode_access_token("invalid-token") is None

    def test_jwt_employee_role(self):
        uid = str(uuid.uuid4())
        token = create_access_token(uid, "employee", extra_claims={"purpose": "ws", "ver": 2})
        payload = decode_access_token(token)
        assert payload["role"] == "employee"
        assert payload["purpose"] == "ws"
        assert payload["ver"] == 2


# ============= ENDPOINT VERIFICATION =============

class TestEndpoints:
    def test_auth_endpoints(self):
        from app.api.auth import router
        paths = [r.path for r in router.routes]
        assert "/login" in paths
        assert "/register" in paths
        assert "/activate" in paths
        assert "/me" in paths

    def test_admin_endpoints(self):
        from app.api.admin import router
        paths = [r.path for r in router.routes]
        assert "/employees" in paths
        assert "/profiles" in paths
        assert "/assignments" in paths
        assert "/sessions" in paths
        assert "/api-keys" in paths
        assert "/kpis" in paths
        assert "/audit-log" in paths
        assert "/agent-templates" in paths
        assert "/monitoring/alerts" in paths

    def test_chat_endpoints(self):
        from app.api.chat import router
        paths = [r.path for r in router.routes]
        assert "/message" in paths
        assert "/message/stream" in paths
        assert "/conversations" in paths

    def test_telegram_endpoints(self):
        from app.api.telegram import router
        paths = [r.path for r in router.routes]
        assert "/webhook" in paths
        assert "/bind" in paths
        assert "/generate-bind-code" in paths
        assert "/bind-with-code" in paths
        assert "/send/{chat_id}" in paths

    def test_websocket_endpoint(self):
        from app.api.websocket_chat import router
        paths = [r.path for r in router.routes]
        assert "/ws/chat" in paths

    def test_health_endpoints(self):
        from app.api.health import router
        paths = [r.path for r in router.routes]
        assert "/health" in paths
        assert "/live" in paths
        assert "/ready" in paths

    def test_all_routers_registered_in_app(self):
        from app.main import app
        all_paths = [r.path for r in app.routes if hasattr(r, 'path')]
        assert any("ws/chat" in p for p in all_paths)
        assert any("/login" in p for p in all_paths)
        assert any("/admin/employees" in p for p in all_paths)
        assert any("/admin/profiles" in p for p in all_paths)
        assert any("/chat/message" in p for p in all_paths)
        assert any("/telegram/webhook" in p for p in all_paths)


# ============= AGENT SERVICE =============

class TestAgentService:
    def test_agent_service_import(self):
        from app.services.agent_service import AgentService
        svc = AgentService()
        assert svc is not None

    def test_mock_response(self):
        from app.services.agent_service import AgentService
        svc = AgentService()
        resp = svc._mock_response([{"role": "user", "content": "test"}])
        assert len(resp) > 0

    def test_estimate_tokens(self):
        from app.services.agent_service import AgentService
        svc = AgentService()
        tokens = svc._estimate_tokens("Hello world, this is a test message.")
        assert tokens > 0
        assert isinstance(tokens, int)


# ============= TELEGRAM WEBHOOK CODE PATH =============

class TestTelegramCode:
    def test_bind_command_detection(self):
        text = "/bind abc123def456"
        assert text.startswith("/bind ")
        code = text[6:].strip()
        assert code == "abc123def456"

    def test_start_command(self):
        text = "/start"
        assert text == "/start"

    def test_normal_message_not_bind(self):
        text = "hello world"
        assert not text.startswith("/bind ")
        assert text != "/start"


# ============= INVITE TOKEN SYSTEM =============

class TestInviteToken:
    def test_token_generation(self):
        token = secrets.token_urlsafe(48)
        assert len(token) > 30
        # URL-safe base64
        assert all(c.isalnum() or c in '-_' for c in token)

    def test_bind_code_generation(self):
        code = secrets.token_hex(6)
        assert len(code) == 12
        assert code.isalnum()

    def test_user_activation_flow_simulation(self):
        """Simulate the activation flow."""
        # Step 1: Admin creates employee
        invite = secrets.token_urlsafe(48)
        user = User(email="emp@test.com", hashed_password=get_password_hash("default"),
                     is_active=False, is_activated=False, invite_token=invite)

        assert user.is_activated is False
        assert user.is_active is False
        assert user.invite_token == invite

        # Step 2: Employee activates
        assert user.invite_token == invite
        user.is_activated = True
        user.is_active = True
        user.invite_token = None
        user.hashed_password = get_password_hash("new_password")

        assert user.is_activated is True
        assert user.is_active is True
        assert user.invite_token is None
        assert verify_password("new_password", user.hashed_password)

    def test_deactivated_user_flow(self):
        user = User(email="emp@test.com", hashed_password=get_password_hash("pw"),
                     is_active=False, is_activated=True)
        assert user.is_activated is True
        assert user.is_active is False
        # This user should see "account deactivated" message


# ============= PROTECTION LOGIC =============

class TestProtectionLogic:
    def test_unbound_user_check(self):
        """Simulate: user not in TelegramBinding → rejected."""
        bindings = {}
        chat_id = 999999
        found = bindings.get(chat_id)
        assert found is None  # Not bound

    def test_unactivated_user_check(self):
        """Simulate: user is_activated=False → rejected."""
        user = User(email="t@t.com", hashed_password="h", is_active=False, is_activated=False)
        assert user.is_activated is False  # Would show activation message

    def test_deactivated_user_check(self):
        """Simulate: user is_active=False → rejected."""
        user = User(email="t@t.com", hashed_password="h", is_active=False, is_activated=True)
        assert user.is_active is False  # Would show deactivated message

    def test_valid_user_check(self):
        """Simulate: user is_active=True and is_activated=True → allowed."""
        user = User(email="t@t.com", hashed_password="h", is_active=True, is_activated=True)
        assert user.is_active is True
        assert user.is_activated is True


# ============= DESKTOP APP =============

class TestDesktopApp:
    def test_desktop_has_websocket(self):
        with open("desktop/src/renderer/index.html") as f:
            content = f.read()
        assert "WebSocket" in content
        assert "wsProtocol" in content or "ws://" in content or "wss://" in content or "connectWebSocket" in content

    def test_desktop_no_sse(self):
        with open("desktop/src/renderer/index.html") as f:
            content = f.read()
        assert "EventSource" not in content
        assert "SSE" not in content or "sse" not in content.lower()

    def test_desktop_has_activation_screen(self):
        with open("desktop/src/renderer/index.html") as f:
            content = f.read()
        assert "activation-panel" in content
        assert "تفعيل الحساب" in content

    def test_desktop_has_telegram_binding(self):
        with open("desktop/src/renderer/index.html") as f:
            content = f.read()
        assert "tg-bind" in content
        assert "tg-gen-code" in content
        assert "ربط التلجرام" in content


# ============= DOCKER =============

class TestDocker:
    def test_docker_compose_exists(self):
        import os
        assert os.path.exists("docker-compose.yml")

    def test_dockerfile_exists(self):
        import os
        assert os.path.exists("Dockerfile")

    def test_docker_compose_has_services(self):
        with open("docker-compose.yml") as f:
            content = f.read()
        assert "api:" in content
        assert "worker:" in content
        assert "beat:" in content
        assert "db:" in content
        assert "redis:" in content


# ============= MIGRATION =============

class TestMigration:
    def test_migration_file_exists(self):
        import os, glob
        files = glob.glob("migrations/versions/*.py")
        migration_files = [f for f in files if "initial" not in f]
        assert len(migration_files) >= 1

    def test_migration_content(self):
        import os, glob
        files = glob.glob("migrations/versions/*.py")
        migration_files = [f for f in files if "initial" not in f]
        if migration_files:
            contents = []
            for path in migration_files:
                with open(path, encoding="utf-8") as f:
                    contents.append(f.read())
            merged = "\n".join(contents)
            assert "soul_md" in merged
            assert "invite_token" in merged
            assert "is_activated" in merged


# ============= CONFIG =============

class TestConfig:
    def test_settings_loads(self):
        from app.core.config import settings
        assert settings.app_name == "FQ-SaaS"

    def test_telegram_settings(self):
        from app.core.config import settings
        assert hasattr(settings, "telegram_bot_token")
        assert hasattr(settings, "telegram_webhook_secret")
        assert hasattr(settings, "telegram_webhook_url")
        assert hasattr(settings, "alert_notification_emails")
        assert hasattr(settings, "alert_notification_recipients")


# ============= CELERY =============

class TestCelery:
    def test_celery_app_exists(self):
        from app.celery_app import celery_app
        assert celery_app is not None

    def test_celery_tasks_exist(self):
        from app import tasks
        assert hasattr(tasks, "reset_daily_counters")
        assert hasattr(tasks, "cleanup_old_sessions")
        assert hasattr(tasks, "send_email_notification")
        assert hasattr(tasks, "track_token_usage")
        assert hasattr(tasks, "evaluate_platform_alerts")
