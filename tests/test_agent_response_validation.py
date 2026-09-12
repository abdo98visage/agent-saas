import pytest

from app.services.agent_service import AgentService


def test_agent_response_validation_rejects_empty_or_whitespace_content():
    with pytest.raises(RuntimeError, match="empty response"):
        AgentService._require_nonempty_response("")
    with pytest.raises(RuntimeError, match="empty response"):
        AgentService._require_nonempty_response("  \n  ")


def test_agent_response_validation_preserves_nonempty_content():
    assert AgentService._require_nonempty_response("answer") == "answer"
