"""Comprehensive Docker feature smoke test for AgentSaaS.

This script intentionally uses only the Python standard library so it can run on a
fresh Windows host or CI runner after the Docker stack is up.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import struct
import sys
import time
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener


Json = dict[str, Any]


class TestFailure(AssertionError):
    pass


def assert_true(value: Any, message: str) -> None:
    if not value:
        raise TestFailure(message)


@dataclass
class ApiClient:
    base_url: str
    token: str | None = None
    timeout_seconds: float = 30.0
    jar: CookieJar = field(default_factory=CookieJar)

    def __post_init__(self) -> None:
        self.opener = build_opener(HTTPCookieProcessor(self.jar))

    def request(
        self,
        method: str,
        path: str,
        body: Json | None = None,
        expected: int | tuple[int, ...] = (200,),
        headers: dict[str, str] | None = None,
        raw: bool = False,
    ) -> Any:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        data = None
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        if self.token:
            request_headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=request_headers, method=method.upper())
        expected_codes = (expected,) if isinstance(expected, int) else expected
        try:
            with self.opener.open(req, timeout=self.timeout_seconds) as response:
                payload = response.read()
                if response.status not in expected_codes:
                    raise TestFailure(f"{method} {path} returned {response.status}, expected {expected_codes}")
                if raw:
                    return payload, dict(response.headers)
                return self._decode(payload, response.headers.get("Content-Type", ""))
        except HTTPError as exc:
            payload = exc.read()
            if exc.code in expected_codes:
                return self._decode(payload, exc.headers.get("Content-Type", ""))
            decoded = self._decode(payload, exc.headers.get("Content-Type", ""))
            raise TestFailure(f"{method} {path} returned {exc.code}, expected {expected_codes}: {decoded}") from exc
        except URLError as exc:
            raise TestFailure(f"{method} {path} failed: {exc}") from exc

    @staticmethod
    def _decode(payload: bytes, content_type: str) -> Any:
        if not payload:
            return None
        text = payload.decode("utf-8", errors="replace")
        if "json" in content_type:
            return json.loads(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


def wait_for_api(client: ApiClient, timeout: int = 90) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status = client.request("GET", "/api/status")
            if status.get("status") == "healthy":
                return
        except Exception:
            pass
        time.sleep(2)
    raise TestFailure("API did not become healthy")


def ws_send(sock: socket.socket, opcode: int, payload: bytes) -> None:
    mask = os.urandom(4)
    first = 0x80 | opcode
    length = len(payload)
    if length < 126:
        header = struct.pack("!BB", first, 0x80 | length)
    elif length < 65536:
        header = struct.pack("!BBH", first, 0x80 | 126, length)
    else:
        header = struct.pack("!BBQ", first, 0x80 | 127, length)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    sock.sendall(header + mask + masked)


def ws_read_frame(sock: socket.socket) -> tuple[int, bytes]:
    header = sock.recv(2)
    if len(header) < 2:
        raise TestFailure("WebSocket closed before frame header")
    first, second = header
    opcode = first & 0x0F
    masked = second & 0x80
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", sock.recv(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", sock.recv(8))[0]
    mask = sock.recv(4) if masked else b""
    payload = b""
    while len(payload) < length:
        chunk = sock.recv(length - len(payload))
        if not chunk:
            raise TestFailure("WebSocket closed while reading frame")
        payload += chunk
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


def websocket_chat(api_url: str, token: str, profile_name: str) -> list[Json]:
    parsed = urlparse(api_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = (
        "/api/chat/ws/chat?"
        + urlencode(
            {
                "token": token,
                "agent_template_name": "default",
                "profile_name": profile_name,
            }
        )
    )
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(45)
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise TestFailure(f"WebSocket handshake failed: {response[:200]!r}")

        events: list[Json] = []
        ws_send(sock, 1, json.dumps({"type": "ping"}).encode("utf-8"))
        ping_deadline = time.time() + 10
        while time.time() < ping_deadline:
            opcode, payload = ws_read_frame(sock)
            if opcode == 9:
                ws_send(sock, 10, payload)
                continue
            if opcode == 8:
                raise TestFailure(f"WebSocket closed by server during ping: {payload!r}")
            if opcode == 1:
                event = json.loads(payload.decode("utf-8"))
                events.append(event)
                if event.get("type") == "pong":
                    break
        else:
            raise TestFailure(f"WebSocket did not acknowledge ping; events={events}")

        ws_send(
            sock,
            1,
            json.dumps(
                {
                    "type": "message",
                    "content": "Write one short WebSocket E2E line.",
                    "project_context": "Docker full feature validation.",
                }
            ).encode("utf-8"),
        )

        deadline = time.time() + 40
        while time.time() < deadline:
            opcode, payload = ws_read_frame(sock)
            if opcode == 9:
                ws_send(sock, 10, payload)
                continue
            if opcode == 8:
                raise TestFailure(f"WebSocket closed by server: {payload!r}")
            if opcode != 1:
                continue
            event = json.loads(payload.decode("utf-8"))
            events.append(event)
            if event.get("type") == "done":
                ws_send(sock, 8, b"")
                close_deadline = time.time() + 5
                while time.time() < close_deadline:
                    try:
                        opcode, payload = ws_read_frame(sock)
                    except (OSError, TestFailure, TimeoutError):
                        break
                    if opcode == 9:
                        ws_send(sock, 10, payload)
                        continue
                    if opcode == 8:
                        break
                return events
            if event.get("type") == "error":
                raise TestFailure(f"WebSocket error event: {event}")
    raise TestFailure(f"WebSocket did not produce a done event; events={events}")


def run_test(name: str, fn) -> None:
    started = time.time()
    try:
        fn()
    except Exception as exc:
        print(f"FAIL {name}: {exc}")
        raise
    elapsed = time.time() - started
    print(f"PASS {name} ({elapsed:.2f}s)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8002")
    parser.add_argument("--admin-url", default="http://localhost:3002")
    parser.add_argument("--admin-email", default="admin@company.com")
    parser.add_argument("--admin-password", default="admin123")
    parser.add_argument("--employee-password", default="Employee123")
    parser.add_argument("--provider", default="minimax")
    parser.add_argument("--model", default="Qwen3.6-27B-IQ4_XS.gguf")
    parser.add_argument("--request-timeout", type=float, default=120.0)
    args = parser.parse_args()

    suffix = base64.b32encode(os.urandom(5)).decode("ascii").lower().rstrip("=")
    admin = ApiClient(args.api_url, timeout_seconds=args.request_timeout)
    employee = ApiClient(args.api_url, timeout_seconds=args.request_timeout)

    state: dict[str, Any] = {
        "profile_name": f"QA Smart Agent {suffix}",
        "profile_slug": f"qa-smart-agent-{suffix}",
        "skill_slug": f"qa-validation-{suffix}",
        "employee_email": f"qa-{suffix}@example.com",
        "chat_id": 900000000 + int.from_bytes(os.urandom(2), "big"),
    }

    def public_health_and_frontend() -> None:
        wait_for_api(admin)
        api_status = admin.request("GET", "/api/status")
        assert_true(api_status.get("status") == "healthy", "API status is not healthy")
        frontend = ApiClient(args.admin_url, timeout_seconds=args.request_timeout)
        html, headers = frontend.request("GET", "/", raw=True)
        assert_true(len(html) > 100, "Admin frontend returned an empty page")
        assert_true("text/html" in headers.get("Content-Type", ""), "Admin frontend did not return HTML")

    def auth_and_session_security() -> None:
        login = admin.request(
            "POST",
            "/api/auth/login",
            {"email": args.admin_email, "password": args.admin_password},
        )
        admin.token = login.get("access_token")
        assert_true(admin.token, "Admin login did not return access token")
        cookie_names = [cookie.name for cookie in admin.jar]
        assert_true("access_token" in cookie_names, "Login did not set access_token cookie")
        me = admin.request("GET", "/api/auth/me")
        assert_true(me.get("email") == args.admin_email, "Auth /me did not return the admin user")
        ApiClient(args.api_url).request("GET", "/api/admin/employees", expected=401)
        admin.request(
            "POST",
            "/api/auth/login",
            {"email": args.admin_email, "password": "wrong-password"},
            expected=401,
        )
        admin.request(
            "POST",
            "/api/auth/register",
            {"email": f"self-{suffix}@example.com", "password": "Password123"},
            expected=403,
        )

    def hermes_control_plane() -> None:
        status = admin.request("GET", "/api/admin/hermes/status")
        assert_true(status.get("running") is True, f"Hermes is not running: {status}")
        logs = admin.request("GET", "/api/admin/hermes/logs?limit=50")
        assert_true(logs.get("status") in {"ok", "managed_externally", "not_available"}, f"Unexpected logs status: {logs}")
        repair = admin.request("POST", "/api/admin/hermes/repair-sync")
        assert_true(repair.get("runtime", {}).get("status") in {"ready", "managed_externally"}, f"Repair-sync failed: {repair}")

    def admin_template_crud() -> None:
        template_name = f"qa-template-{suffix}"
        created = admin.request(
            "POST",
            "/api/admin/agent-templates",
            {
                "name": template_name,
                "department": "qa",
                "system_prompt": "Answer for Docker full feature validation.",
                "tools": ["local_runtime"],
                "model_name": args.model,
                "max_tokens_per_request": 2000,
                "temperature": 0.2,
            },
            expected=201,
        )
        assert_true(created.get("name") == template_name, "Template create returned wrong name")
        admin.request("PUT", f"/api/admin/agent-templates/{template_name}", {"temperature": 0.3})
        listed = admin.request("GET", "/api/admin/agent-templates")
        assert_true(any(t["name"] == template_name for t in listed.get("templates", [])), "Template not listed")
        admin.request("DELETE", f"/api/admin/agent-templates/{template_name}")
        listed_after = admin.request("GET", "/api/admin/agent-templates")
        assert_true(not any(t["name"] == template_name for t in listed_after.get("templates", [])), "Template delete did not persist")
        admin.request(
            "PUT",
            "/api/admin/agent-templates/default",
            {
                "model_name": args.model,
                "max_tokens_per_request": 256,
                "temperature": 0.1,
                "system_prompt": "Reply with a short direct final answer.",
            },
        )

    def admin_skill_crud() -> None:
        created = admin.request(
            "POST",
            "/api/admin/skills",
            {
                "name": f"QA Validation {suffix}",
                "slug": state["skill_slug"],
                "description": "Reusable end-to-end validation skill.",
                "instructions_md": "Validate the requested workflow and return a concise result.",
                "is_active": True,
            },
            expected=201,
        )
        state["skill_id"] = created["id"]
        updated = admin.request(
            "PUT",
            f"/api/admin/skills/{state['skill_id']}",
            {"description": "Updated reusable end-to-end validation skill."},
        )
        assert_true(updated.get("description", "").startswith("Updated"), "Skill update did not persist")
        listed = admin.request("GET", "/api/admin/skills?include_inactive=true")
        assert_true(
            any(skill["id"] == state["skill_id"] for skill in listed.get("skills", [])),
            "Skill not listed",
        )

    def profile_key_employee_assignment_flow() -> None:
        profile = admin.request(
            "POST",
            "/api/admin/profiles",
            {
                "name": state["profile_name"],
                "slug": state["profile_slug"],
                "runtime_type": "hermes",
                "agents_md": "# QA Smart Agent\nValidate Docker execution.",
                "soul_md": "Reliable QA assistant.",
                "skills": [state["skill_slug"]],
                "system_prompt": "Respond concisely for Docker validation.",
                "max_tokens_per_day": 100000,
                "max_requests_per_day": 1000,
                "daily_cost_budget": 100000,
                "allowed_providers": [args.provider],
                "allowed_tools": ["local_runtime"],
                "allowed_mcp_servers": [],
            },
            expected=201,
        )
        state["profile_id"] = profile["id"]
        assert_true(profile.get("hermes_sync_status") == "synced", f"Profile did not sync: {profile}")
        update = admin.request(
            "PUT",
            f"/api/admin/profiles/{state['profile_id']}",
            {"skills": [state["skill_slug"]], "system_prompt": "Updated Docker validation prompt."},
        )
        assert_true(update.get("hermes_sync_status") == "synced", f"Profile update did not sync: {update}")
        sync = admin.request("POST", f"/api/admin/profiles/{state['profile_id']}/sync")
        assert_true(sync.get("hermes_sync_status") == "synced", f"Manual sync failed: {sync}")

        profile_key = admin.request(
            "POST",
            "/api/admin/api-keys",
            {
                "owner_type": "profile",
                "profile_id": state["profile_id"],
                "provider": args.provider,
                "api_key": "sk-e2e-profile-key",
                "daily_budget": 100000,
            },
            expected=201,
        )
        state["profile_key_id"] = profile_key["id"]
        platform_key = admin.request(
            "POST",
            "/api/admin/api-keys",
            {
                "owner_type": "platform",
                "provider": args.provider,
                "api_key": "sk-e2e-platform-key",
                "daily_budget": 100000,
            },
            expected=201,
        )
        state["platform_key_id"] = platform_key["id"]
        admin.request("PUT", f"/api/admin/api-keys/{state['platform_key_id']}", {"daily_budget": 110000})

        employee_row = admin.request(
            "POST",
            "/api/admin/employees",
            {
                "email": state["employee_email"],
                "full_name": "QA Docker Employee",
                "department": "qa",
                "role": "employee",
                "max_tokens_per_day": 100000,
                "max_requests_per_day": 1000,
            },
            expected=201,
        )
        state["employee_id"] = employee_row["id"]
        state["invite_token"] = employee_row["invite_token"]
        user_key = admin.request(
            "POST",
            "/api/admin/api-keys",
            {
                "owner_type": "user",
                "user_id": state["employee_id"],
                "provider": args.provider,
                "api_key": "sk-e2e-user-key",
                "daily_budget": 100000,
            },
            expected=201,
        )
        state["user_key_id"] = user_key["id"]
        admin.request("PUT", f"/api/admin/employees/{state['employee_id']}", {"full_name": "QA Docker Employee Updated"})
        admin.request(
            "PUT",
            f"/api/admin/employees/{state['employee_id']}/quotas",
            {"max_tokens_per_day": 120000, "max_requests_per_day": 1200},
        )
        assignment = admin.request(
            "POST",
            "/api/admin/assignments",
            {"user_id": state["employee_id"], "profile_id": state["profile_id"], "priority": 0},
            expected=201,
        )
        state["assignment_id"] = assignment["id"]
        listed = admin.request("GET", "/api/admin/assignments")
        assert_true(any(item["id"] == state["assignment_id"] for item in listed.get("assignments", [])), "Assignment not listed")

    def employee_activation_and_isolation() -> None:
        activation = employee.request(
            "POST",
            "/api/auth/activate",
            {"token": state["invite_token"], "password": args.employee_password},
        )
        employee.token = activation.get("access_token")
        assert_true(employee.token, "Employee activation did not return token")
        me = employee.request("GET", "/api/auth/me")
        assert_true(me.get("email") == state["employee_email"], "Employee /me returned wrong user")
        employee.request("GET", "/api/admin/employees", expected=403)

    def chat_rest_sse_and_history() -> None:
        chat = employee.request(
            "POST",
            "/api/chat/message",
            {
                "message": "Write one short REST E2E response.",
                "profile_name": state["profile_name"],
                "agent_template_name": "default",
                "project_context": "Docker full validation.",
            },
        )
        state["conversation_id"] = chat["conversation_id"]
        assert_true(chat.get("content"), "REST chat returned empty content")
        assert_true(chat.get("tokens_used", 0) > 0, "REST chat did not report tokens")

        conversations = employee.request("GET", "/api/chat/conversations")
        assert_true(any(c["conversation_id"] == state["conversation_id"] for c in conversations.get("conversations", [])), "Conversation not listed")
        messages = employee.request("GET", f"/api/chat/conversations/{state['conversation_id']}/messages")
        assert_true(messages.get("count", 0) >= 2, "Conversation messages missing user/assistant records")
        titled = employee.request("POST", f"/api/chat/conversations/{state['conversation_id']}/title?title={quote('QA Conversation')}")
        assert_true(titled.get("title") == "QA Conversation", "Conversation title update failed")

        stream, _ = employee.request(
            "POST",
            "/api/chat/message/stream",
            {
                "message": "Write one short SSE E2E response.",
                "profile_name": state["profile_name"],
                "agent_template_name": "default",
                "project_context": "Docker full validation.",
            },
            raw=True,
        )
        text = stream.decode("utf-8", errors="replace")
        assert_true("event: start" in text and "event: done" in text, f"SSE stream missing events: {text[:200]}")

    def websocket_streaming() -> None:
        ws_token = employee.request("POST", "/api/auth/ws-token")
        assert_true(ws_token.get("expires_in") == 300, "ws-token did not return expected TTL")
        events = websocket_chat(args.api_url, ws_token["access_token"], state["profile_name"])
        types = {event.get("type") for event in events}
        assert_true({"start", "chunk", "done"}.issubset(types), f"WebSocket missing events: {events}")

    def telegram_flow() -> None:
        bind = employee.request("POST", "/api/telegram/generate-bind-code")
        bind_code = bind.get("bind_code")
        assert_true(bind_code, f"Did not receive bind code: {bind}")
        unbound = ApiClient(args.api_url).request(
            "POST",
            "/api/telegram/webhook",
            {"message": {"chat": {"id": state["chat_id"]}, "text": "/start"}},
        )
        assert_true(unbound.get("bound") is False, "Telegram /start should be unbound before binding")
        webhook_bind = ApiClient(args.api_url).request(
            "POST",
            "/api/telegram/webhook",
            {"message": {"chat": {"id": state["chat_id"]}, "text": f"/bind {bind_code}"}},
        )
        assert_true(webhook_bind.get("bound") is True, f"Telegram webhook bind failed: {webhook_bind}")
        confirm = employee.request("POST", "/api/telegram/bind-with-code", {"binding_code": bind_code})
        assert_true(confirm.get("telegram_chat_id") == state["chat_id"], "Telegram bind confirmation returned wrong chat id")
        reply = ApiClient(args.api_url).request(
            "POST",
            "/api/telegram/webhook",
            {"message": {"chat": {"id": state["chat_id"]}, "text": "Write a short Telegram E2E reply."}},
        )
        assert_true(reply.get("bound") is True and reply.get("response"), f"Telegram reply failed: {reply}")

    def observability_and_admin_lists() -> None:
        session = admin.request("GET", f"/api/admin/sessions/{state['conversation_id']}")
        assert_true(session.get("count", 0) >= 2, "Admin session view is missing messages")
        assert_true(session.get("runs"), "Admin session view is missing run records")
        assert_true(session["runs"][0].get("runtime_type") == "hermes", "Run record is not Hermes")
        kpis = admin.request("GET", "/api/admin/kpis")
        assert_true(kpis.get("count", 0) >= 1, "KPIs are empty")
        dashboard = admin.request("GET", "/api/admin/monitoring/dashboard-stats")
        assert_true(dashboard.get("summary", {}).get("messages_today", 0) >= 1, "Dashboard did not count messages")
        online = admin.request("GET", "/api/admin/monitoring/online-users")
        assert_true("online_users" in online, "Online users response missing online_users")
        activity = admin.request("GET", "/api/admin/monitoring/activity-feed?limit=20")
        assert_true("activities" in activity, "Activity feed response missing activities")
        audit = admin.request("GET", "/api/admin/audit-log?limit=50")
        assert_true(audit.get("count", 0) >= 1, "Audit log is empty")
        employees = admin.request("GET", "/api/admin/employees")
        assert_true(any(e["email"] == state["employee_email"] for e in employees.get("employees", [])), "Employee not in final listing")
        profiles = admin.request("GET", "/api/admin/profiles")
        assert_true(any(p["slug"] == state["profile_slug"] for p in profiles.get("profiles", [])), "Profile not in final listing")
        api_keys = admin.request("GET", "/api/admin/api-keys")
        assert_true(len(api_keys.get("api_keys", [])) >= 3, "API keys listing did not include created keys")

    tests = [
        ("public health and admin frontend", public_health_and_frontend),
        ("auth, cookies, and access control", auth_and_session_security),
        ("agent control plane", hermes_control_plane),
        ("admin agent template CRUD", admin_template_crud),
        ("admin skill CRUD", admin_skill_crud),
        ("profiles, API keys, employees, assignments", profile_key_employee_assignment_flow),
        ("employee activation and admin isolation", employee_activation_and_isolation),
        ("chat REST, SSE, conversations, history", chat_rest_sse_and_history),
        ("chat WebSocket streaming", websocket_streaming),
        ("Telegram bind and webhook flow", telegram_flow),
        ("observability and admin listings", observability_and_admin_lists),
    ]

    for name, fn in tests:
        run_test(name, fn)

    print("SUMMARY all Docker feature checks passed")
    print(f"PROFILE {state['profile_slug']}")
    print(f"EMPLOYEE {state['employee_email']}")
    print(f"CONVERSATION {state.get('conversation_id', '')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TestFailure:
        raise SystemExit(1)
