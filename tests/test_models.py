"""Model tests — verify all fields exist and have correct types."""
import secrets
import uuid
import pytest
from app.models.user import User
from app.models.profile import Profile
from app.models.telegram_binding import TelegramBinding
from app.models.session import Session
from app.models.message import Message
from app.models.agent_template import AgentTemplate
from app.models.kpi import KPI
from app.models.audit_log import AuditLog
from app.models.user_api_key import UserApiKey
from app.models.profile_user import ProfileUser
from app.models.agent_run import AgentRun, AgentRunEvent
from app.models.provider_pricing import ProviderPricing
from app.models.alert_event import AlertEvent


class TestUserModel:
    def test_user_has_new_fields(self):
        assert hasattr(User, "invite_token")
        assert hasattr(User, "is_activated")
        assert hasattr(User, "is_active")
        assert hasattr(User, "role")
        assert hasattr(User, "token_version")

    def test_pending_employee(self):
        u = User(
            email="new@test.com", hashed_password="hash",
            is_active=False, is_activated=False,
            invite_token=secrets.token_urlsafe(48),
        )
        assert u.is_activated is False
        assert u.is_active is False
        assert len(u.invite_token) > 20
        assert hasattr(u, "invite_token_expires_at")

    def test_admin_user(self):
        u = User(
            email="admin@test.com", hashed_password="hash",
            role="admin", is_active=True, is_activated=True,
        )
        assert u.role == "admin"
        assert u.is_activated is True


class TestProfileModel:
    def test_profile_has_soul_md(self):
        p = Profile(name="test", slug="test", soul_md="soul", agents_md="agents")
        assert hasattr(p, "soul_md")
        assert p.soul_md == "soul"
        assert p.agents_md == "agents"

    def test_profile_no_description(self):
        assert not hasattr(Profile, "description")

    def test_profile_required_fields(self):
        p = Profile(name="test", slug="test")
        # name and slug are required, rest have defaults
        assert p.name == "test"
        assert p.slug == "test"

    def test_profile_has_hermes_runtime_fields(self):
        p = Profile(name="marketing", slug="marketing")
        assert hasattr(p, "runtime_type")
        assert hasattr(p, "hermes_sync_status")
        assert hasattr(p, "version")
        assert hasattr(p, "allowed_mcp_servers")


class TestTelegramBindingModel:
    def test_binding_fields(self):
        uid = uuid.uuid4()
        b = TelegramBinding(
            user_id=uid, telegram_chat_id=0, binding_token=secrets.token_hex(6)
        )
        assert b.user_id == uid
        assert b.telegram_chat_id == 0
        assert len(b.binding_token) == 12
        assert hasattr(b, "binding_token_expires_at")


class TestSessionModel:
    def test_session_fields(self):
        uid = uuid.uuid4()
        s = Session(user_id=uid, agent_template_name="default")
        assert s.user_id == uid
        assert s.agent_template_name == "default"


class TestMessageModel:
    def test_message_fields(self):
        sid = uuid.uuid4()
        m = Message(session_id=sid, role="user", content="hello")
        assert m.session_id == sid
        assert m.role == "user"
        assert m.content == "hello"


class TestAgentTemplateModel:
    def test_template_fields(self):
        t = AgentTemplate(
            name="default", system_prompt="be helpful",
            model_name="qwen3-14b", temperature=0.7,
        )
        assert t.name == "default"
        assert t.model_name == "qwen3-14b"
        assert t.temperature == 0.7


class TestKPIModel:
    def test_kpi_fields(self):
        uid = "user-uuid-000000000000000000000000"
        k = KPI(user_id=uid, date="2026-06-12")
        assert k.user_id == uid
        assert k.date == "2026-06-12"


class TestAuditLogModel:
    def test_audit_log_fields(self):
        a = AuditLog(user_id="admin-uuid", action="add_employee", details={"email": "x"})
        assert a.action == "add_employee"
        assert a.details == {"email": "x"}


class TestUserApiKeyModel:
    def test_api_key_fields(self):
        uid = uuid.uuid4()
        k = UserApiKey(
            owner_type="user", user_id=uid, provider="minimax", encrypted_key="enc", key_prefix="sk-123"
        )
        assert k.owner_type == "user"
        assert k.provider == "minimax"
        assert k.key_prefix == "sk-123"


class TestProfileUserModel:
    def test_profile_user_fields(self):
        uid = uuid.uuid4()
        pid = uuid.uuid4()
        pu = ProfileUser(user_id=uid, profile_id=pid, priority=5)
        assert pu.user_id == uid
        assert pu.profile_id == pid
        assert pu.priority == 5


class TestAgentRunModel:
    def test_agent_run_fields(self):
        sid = uuid.uuid4()
        uid = uuid.uuid4()
        run = AgentRun(session_id=sid, user_id=uid, runtime_type="hermes", status="running")
        assert run.session_id == sid
        assert run.user_id == uid
        assert run.runtime_type == "hermes"
        assert hasattr(run, "pricing_snapshot")

    def test_agent_run_event_fields(self):
        rid = uuid.uuid4()
        event = AgentRunEvent(run_id=rid, event_type="tool_call", payload={"name": "search"})
        assert event.run_id == rid
        assert event.event_type == "tool_call"
        assert event.payload == {"name": "search"}


class TestProviderPricingModel:
    def test_provider_pricing_fields(self):
        pricing = ProviderPricing(
            provider="minimax",
            monthly_price_usd=20.0,
            monthly_token_allowance=1_700_000_000,
            currency="USD",
        )
        assert pricing.provider == "minimax"
        assert pricing.monthly_price_usd == 20.0
        assert pricing.monthly_token_allowance == 1_700_000_000


class TestAlertEventModel:
    def test_alert_event_fields(self):
        alert = AlertEvent(
            alert_type="hermes_runtime",
            severity="critical",
            status="active",
            title="Hermes runtime is unhealthy",
            message="Runtime is down",
            fingerprint="hermes_runtime",
            context={"status": "down"},
            first_seen_at=__import__("datetime").datetime.utcnow(),
            last_seen_at=__import__("datetime").datetime.utcnow(),
        )
        assert alert.alert_type == "hermes_runtime"
        assert alert.severity == "critical"
        assert alert.fingerprint == "hermes_runtime"
