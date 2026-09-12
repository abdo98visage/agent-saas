from types import SimpleNamespace
from uuid import uuid4
from pathlib import Path
import shutil
from datetime import datetime, timedelta

from app.local_hermes_runtime_app import _build_prompt
from app.services.agent_runtime import HermesRuntime
from app.services.agent_service import AgentService
import app.local_hermes_runtime_app as local_runtime


def test_hermes_payload_includes_conversation_history():
    user_id = uuid4()
    profile_id = uuid4()
    runtime = HermesRuntime()
    history = [
        {"role": "user", "content": "What is in note.txt?"},
        {"role": "assistant", "content": "I found note.txt. Should I read it?"},
    ]

    payload = runtime._payload(
        user=SimpleNamespace(
            id=user_id,
            email="employee@example.com",
            full_name="Employee",
            department="Accounting",
        ),
        profile=SimpleNamespace(
            id=profile_id,
            slug="accounting",
            name="Accounting",
            version=3,
            hermes_profile_id="accounting",
        ),
        session_id=str(uuid4()),
        user_message="yes",
        project_context=None,
        api_key="test-key",
        model="test-model",
        provider="mock",
        conversation_history=history,
    )

    assert payload["history"] == history
    assert payload["message"] == "yes"


def test_local_hermes_prompt_uses_history_for_short_followups(monkeypatch):
    temp_root = Path(".pytest_cache") / "hermes-history-test"
    shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(local_runtime, "HERMES_PROFILES_ROOT", temp_root)
    payload = {
        "employee": {"email": "employee@example.com", "full_name": "Employee"},
        "profile": {"slug": "accounting"},
        "history": [
            {"role": "user", "content": "What is in note.txt?"},
            {"role": "assistant", "content": "I found note.txt. Should I read it?"},
        ],
        "message": "yes",
    }

    prompt = _build_prompt(payload)

    assert "Conversation continuity rule" in prompt
    assert "Conversation history before the latest user request" in prompt
    assert "What is in note.txt?" in prompt
    assert "Should I read it?" in prompt
    assert "Primary user request" in prompt
    assert "yes" in prompt


def test_local_hermes_prompt_keeps_bounded_anchors_with_twenty_recent_messages(monkeypatch):
    temp_root = Path(".pytest_cache") / "hermes-long-history-runtime-test"
    shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(local_runtime, "HERMES_PROFILES_ROOT", temp_root)
    history = [
        {"role": "user", "content": "The project codename is ORCHID-581"},
        {"role": "assistant", "content": "ACK"},
        *[
            {"role": "user" if index % 2 == 0 else "assistant", "content": f"recent-{index}"}
            for index in range(20)
        ],
    ]

    prompt = _build_prompt({
        "employee": {"email": "employee@example.com"},
        "profile": {"slug": "accounting"},
        "history": history,
        "message": "What is the project codename?",
    })

    assert "The project codename is ORCHID-581" in prompt
    assert "recent-19" in prompt


def test_long_conversation_history_keeps_anchors_and_relevant_older_turns():
    import asyncio

    class ScalarResult:
        def __init__(self, rows):
            self.rows = rows

        def scalars(self):
            return self

        def all(self):
            return self.rows

    class DbStub:
        def __init__(self, result_sets):
            self.result_sets = iter(result_sets)

        async def execute(self, _query):
            return ScalarResult(next(self.result_sets))

    started = datetime(2026, 1, 1)

    def message(index, content):
        return SimpleNamespace(
            id=uuid4(), role="user" if index % 2 == 0 else "assistant",
            content=content, attachments=[], created_at=started + timedelta(seconds=index),
        )

    anchor = message(0, "The project codename is ORCHID-581")
    relevant = message(6, "The approved project owner is Mira")
    recent = [message(index, f"recent-{index}") for index in range(10, 30)]
    db = DbStub([list(reversed(recent)), [anchor], [relevant]])

    async def scenario():
        history = await AgentService()._load_conversation_history(
            db, uuid4(), "openai", "What is the project codename and owner?",
        )
        contents = [item["content"] for item in history]
        assert contents[0] == "The project codename is ORCHID-581"
        assert contents[1] == "The approved project owner is Mira"
        assert contents[-1] == "recent-29"
        assert len(contents) == 22

    asyncio.run(scenario())
