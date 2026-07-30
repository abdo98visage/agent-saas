from types import SimpleNamespace
from uuid import uuid4
from pathlib import Path
import shutil

from app.local_hermes_runtime_app import _build_prompt
from app.services.agent_runtime import HermesRuntime
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
