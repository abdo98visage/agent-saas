"""
WebSocket and streaming endpoint tests.
Run: pytest tests/test_websocket.py -v
"""
import json
import pytest


class TestWebSocketRoute:
    """Test WebSocket route registration."""

    def test_websocket_route_registered(self):
        """Test that WebSocket route is registered."""
        from app.main import app
        ws_routes = [r for r in app.routes if hasattr(r, 'path') and 'ws/chat' in r.path]
        assert len(ws_routes) == 1
        assert ws_routes[0].path == "/api/chat/ws/chat"

    def test_sse_still_available(self):
        """Test SSE streaming endpoint still works alongside WebSocket."""
        from app.main import app
        sse_routes = [r for r in app.routes if hasattr(r, 'path') and 'message/stream' in r.path]
        assert len(sse_routes) >= 1

    def test_all_routers_loaded(self):
        """Test all API routers are loaded."""
        from app.main import app
        tags = set()
        for r in app.routes:
            if hasattr(r, 'tags') and r.tags:
                tags.update(r.tags)
        expected = {"Health", "Auth", "Chat", "Admin", "Telegram"}
        assert expected.issubset(tags), f"Missing tags: {expected - tags}"
        # WebSocket route is separate (not HTTP router)
        ws_routes = [r for r in app.routes if hasattr(r, 'path') and 'ws/chat' in r.path]
        assert len(ws_routes) == 1


class TestAgentService:
    """Test AgentService streaming."""

    def test_mock_response(self):
        """Test mock LLM response."""
        from app.services.agent_service import AgentService
        service = AgentService()
        result = service._mock_response([{"role": "user", "content": "Hello"}])
        assert "Hello" in result
        assert "[Mock]" in result

    def test_estimate_tokens(self):
        """Test token estimation."""
        from app.services.agent_service import AgentService
        assert AgentService._estimate_tokens("") == 0
        assert AgentService._estimate_tokens("Hello") >= 1
        assert AgentService._estimate_tokens("A" * 400) == 100

    def test_agent_service_import(self):
        """Test AgentService imports correctly."""
        from app.services.agent_service import AgentService
        service = AgentService()
        assert hasattr(service, 'run_agent')
        assert hasattr(service, 'run_agent_stream')
        assert hasattr(service, '_call_llm')
        assert hasattr(service, '_call_llm_stream')


class TestWebSocketModule:
    """Test WebSocket module."""

    def test_websocket_chat_module(self):
        """Test websocket_chat module imports."""
        from app.api import websocket_chat
        assert hasattr(websocket_chat, 'router')
        assert hasattr(websocket_chat, 'websocket_chat')
        assert hasattr(websocket_chat, 'get_websocket_user')
        assert hasattr(websocket_chat, 'track_kpi')

    def test_websocket_endpoint_has_auth(self):
        """Test WebSocket endpoint requires authentication."""
        from app.api.websocket_chat import websocket_chat
        import inspect
        source = inspect.getsource(websocket_chat)
        assert "get_websocket_user" in source
        assert "Authentication failed" in source

    def test_websocket_endpoint_handles_events(self):
        """Test WebSocket endpoint handles all event types."""
        from app.api import websocket_chat
        import inspect
        source = inspect.getsource(websocket_chat)
        for event_type in ["start", "chunk", "assistant_chunk", "tool_request", "approval_required", "apply_request", "done", "error", "ping", "pong", "tool_result", "apply_result", "user_message"]:
            assert f'"{event_type}"' in source, f"Missing event type: {event_type}"

    def test_websocket_endpoint_supports_profile_override(self):
        """Test WebSocket endpoint accepts per-message profile override."""
        from app.api.websocket_chat import websocket_chat
        import inspect
        source = inspect.getsource(websocket_chat)
        assert 'msg.get("profile_name") or profile_name' in source
        assert 'profile_name=effective_profile_name' in source


class TestAuthProfileAssignment:
    """Test assigned profile API contract."""

    def test_assigned_profiles_endpoint_exists(self):
        """Test auth router exposes assigned profile listing."""
        from app.api.auth import get_assigned_profiles
        import inspect
        source = inspect.getsource(get_assigned_profiles)
        assert "assigned-profiles" in source or "profiles" in source
        assert "ProfileUser" in source
        assert "runtime_type" in source


class TestDesktopWebSocketClient:
    """Test Desktop app WebSocket client code."""

    def test_desktop_has_websocket_code(self):
        """Test Desktop app has WebSocket client code."""
        with open("desktop/src/renderer/index.html") as f:
            content = f.read()
        assert "WebSocket" in content
        assert "connectWebSocket" in content
        assert "handleWsMessage" in content
        assert "sendWebSocketMessage" in content

    def test_desktop_no_sse_code(self):
        """Test Desktop app no longer uses SSE."""
        with open("desktop/src/renderer/index.html") as f:
            content = f.read()
        # Should not have SSE-specific code
        assert "EventSource" not in content
        assert "message/stream" not in content

    def test_desktop_supports_assigned_profile_picker(self):
        """Test Desktop app exposes assigned profile selection."""
        with open("desktop/src/renderer/index.html") as f:
            content = f.read()
        assert "setting-profile" in content
        assert "/auth/assigned-profiles" in content
        assert "profile_name" in content
        assert "tool_result" in content
        assert "apply_result" in content
        assert "user_message" in content

    def test_desktop_synced_with_dist(self):
        """Test that dist/ matches src/."""
        with open("desktop/src/renderer/index.html") as f:
            src = f.read()
        with open("desktop/src/renderer/dist/index.html") as f:
            dist = f.read()
        assert src == dist, "dist/index.html is not synced with src/"
