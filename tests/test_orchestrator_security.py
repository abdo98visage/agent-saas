import json

import pytest

import app.hermes_orchestrator_app as orchestrator


def test_model_credential_is_replaced_before_runtime(monkeypatch):
    monkeypatch.setattr(
        orchestrator,
        "HERMES_MODEL_PROXY_URL",
        "http://hermes-orchestrator:8788/internal/model/v1/chat/completions",
    )
    payload = {
        "provider": "openai",
        "api_key": "provider-secret",
        "message": "hello",
    }
    runtime_payload, token = orchestrator._prepare_runtime_payload(payload)
    try:
        assert token
        assert runtime_payload["api_key"] == token
        assert runtime_payload["provider_base_url"].startswith("http://hermes-orchestrator:")
        assert "provider-secret" not in json.dumps(runtime_payload)
        assert orchestrator._model_proxy_runs[token]["api_key"] == "provider-secret"
    finally:
        orchestrator._model_proxy_runs.pop(token, None)


def test_model_proxy_rejects_unknown_or_expired_token():
    with pytest.raises(Exception) as exc_info:
        orchestrator._provider_proxy_session("missing")
    assert getattr(exc_info.value, "status_code", None) == 401


def test_keyless_provider_does_not_create_proxy_session():
    payload, token = orchestrator._prepare_runtime_payload({"provider": "mock", "api_key": ""})
    assert token is None
    assert payload == {"provider": "mock", "api_key": ""}


def test_orchestrator_authenticates_every_private_runtime_call(monkeypatch):
    monkeypatch.setattr(orchestrator, "HERMES_RUNTIME_SECRET", "separate-runtime-secret")
    assert orchestrator._runtime_headers() == {
        "X-Hermes-Runtime-Secret": "separate-runtime-secret"
    }
