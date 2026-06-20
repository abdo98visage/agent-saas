"""Validate direct_llm profiles against an OpenAI-compatible endpoint."""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import struct
import time
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
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
    jar: CookieJar = field(default_factory=CookieJar)

    def __post_init__(self) -> None:
        self.opener = build_opener(HTTPCookieProcessor(self.jar))

    def request(
        self,
        method: str,
        path: str,
        body: Json | None = None,
        expected: int | tuple[int, ...] = (200,),
        raw: bool = False,
    ) -> Any:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        data = None
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers, method=method.upper())
        expected_codes = (expected,) if isinstance(expected, int) else expected
        try:
            with self.opener.open(req, timeout=60) as response:
                payload = response.read()
                if response.status not in expected_codes:
                    raise TestFailure(f"{method} {path} returned {response.status}, expected {expected_codes}")
                if raw:
                    return payload
                return self._decode(payload, response.headers.get("Content-Type", ""))
        except HTTPError as exc:
            payload = exc.read()
            decoded = self._decode(payload, exc.headers.get("Content-Type", ""))
            if exc.code in expected_codes:
                return decoded
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
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status = client.request("GET", "/api/status")
            if status.get("status") == "healthy":
                return
        except Exception as exc:  # pragma: no cover - polling path
            last_error = exc
        time.sleep(2)
    raise TestFailure(f"API did not become healthy: {last_error}")


def ws_send(sock: socket.socket, opcode: int, payload: bytes) -> None:
    mask = b"test"
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


def websocket_chat(api_url: str, token: str, profile_name: str, agent_template_name: str) -> list[Json]:
    parsed = urlparse(api_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 80
    path = (
        "/api/chat/ws/chat?"
        + urlencode(
            {
                "token": token,
                "agent_template_name": agent_template_name,
                "profile_name": profile_name,
            }
        )
    )
    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(60)
        ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise TestFailure(f"WebSocket handshake failed: {response[:200]!r}")

        ws_send(
            sock,
            1,
            json.dumps(
                {
                    "type": "message",
                    "content": "Reply with DIRECT_LLM_OK only.",
                    "project_context": "Validate direct_llm over local llama.cpp.",
                }
            ).encode("utf-8"),
        )

        events: list[Json] = []
        deadline = time.time() + 60
        while time.time() < deadline:
            opcode, payload = ws_read_frame(sock)
            if opcode == 9:
                ws_send(sock, 10, payload)
                continue
            if opcode == 8:
                break
            if opcode != 1:
                continue
            event = json.loads(payload.decode("utf-8"))
            events.append(event)
            if event.get("type") == "done":
                ws_send(sock, 8, b"")
                return events
        raise TestFailure(f"WebSocket did not finish: {events}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8002")
    parser.add_argument("--admin-email", default="admin@company.com")
    parser.add_argument("--admin-password", default="admin123")
    parser.add_argument("--employee-password", default="Employee123")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default="Qwen3.6-27B-IQ4_XS.gguf")
    args = parser.parse_args()

    admin = ApiClient(args.api_url)
    employee = ApiClient(args.api_url)
    wait_for_api(admin)

    login = admin.request(
        "POST",
        "/api/auth/login",
        {"email": args.admin_email, "password": args.admin_password},
    )
    admin.token = login["access_token"]

    suffix = str(int(time.time()))
    profile_name = f"Direct LLM {suffix}"
    profile_slug = f"direct-llm-{suffix}"
    employee_email = f"direct-{suffix}@example.com"
    template_name = f"direct-llm-{suffix}"

    template = admin.request(
        "POST",
        "/api/admin/agent-templates",
        {
            "name": template_name,
            "department": "qa",
            "system_prompt": "Reply with DIRECT_LLM_OK only.",
            "tools": [],
            "model_name": args.model,
            "max_tokens_per_request": 256,
            "temperature": 0.0,
        },
        expected=201,
    )
    assert_true(template.get("name") == template_name, "Direct LLM test template was not created")

    profile = admin.request(
        "POST",
        "/api/admin/profiles",
        {
            "name": profile_name,
            "slug": profile_slug,
            "runtime_type": "direct_llm",
            "agents_md": "# Direct LLM Test\nUse the configured OpenAI-compatible backend.",
            "soul_md": "Answer tersely.",
            "skills": ["qa", "llama.cpp"],
            "system_prompt": "Reply with DIRECT_LLM_OK only.",
            "max_tokens_per_day": 100000,
            "max_requests_per_day": 1000,
            "daily_cost_budget": 100000,
            "allowed_providers": [args.provider],
            "allowed_tools": [],
            "allowed_mcp_servers": [],
        },
        expected=201,
    )
    assert_true(profile.get("id"), "Direct LLM profile was not created")

    api_key = admin.request(
        "POST",
        "/api/admin/api-keys",
        {
            "owner_type": "profile",
            "profile_id": profile["id"],
            "provider": args.provider,
            "api_key": "local-llama-placeholder",
            "daily_budget": 100000,
        },
        expected=201,
    )
    assert_true(api_key.get("id"), "Profile API key was not created")

    employee_row = admin.request(
        "POST",
        "/api/admin/employees",
        {
            "email": employee_email,
            "full_name": "Direct LLM Employee",
            "department": "qa",
            "role": "employee",
            "max_tokens_per_day": 100000,
            "max_requests_per_day": 1000,
        },
        expected=201,
    )
    assignment = admin.request(
        "POST",
        "/api/admin/assignments",
        {"user_id": employee_row["id"], "profile_id": profile["id"], "priority": 0},
        expected=201,
    )
    assert_true(assignment.get("id"), "Assignment was not created")

    activation = employee.request(
        "POST",
        "/api/auth/activate",
        {"token": employee_row["invite_token"], "password": args.employee_password},
    )
    employee.token = activation["access_token"]

    rest = employee.request(
        "POST",
        "/api/chat/message",
        {
            "message": "Reply with DIRECT_LLM_OK only.",
            "profile_name": profile_name,
            "agent_template_name": template_name,
            "project_context": "Confirm we are hitting llama.cpp via direct_llm.",
        },
    )
    assert_true(rest.get("content") is not None, "REST direct_llm response was empty")
    assert_true(rest.get("conversation_id"), "REST direct_llm did not create a conversation")

    stream_bytes = employee.request(
        "POST",
        "/api/chat/message/stream",
        {
            "message": "Reply with DIRECT_LLM_OK only.",
            "profile_name": profile_name,
            "agent_template_name": template_name,
            "project_context": "Validate SSE against llama.cpp.",
        },
        raw=True,
    )
    stream_text = stream_bytes.decode("utf-8", errors="replace")
    assert_true("event: done" in stream_text, "SSE direct_llm stream did not finish")

    ws_token = employee.request("POST", "/api/auth/ws-token")
    ws_events = websocket_chat(args.api_url, ws_token["access_token"], profile_name, template_name)
    event_types = {event.get("type") for event in ws_events}
    assert_true({"chunk", "done"}.issubset(event_types), f"WebSocket direct_llm missing events: {ws_events}")

    session = admin.request("GET", f"/api/admin/sessions/{rest['conversation_id']}")
    assert_true(session.get("runs"), "Admin session is missing run records")
    assert_true(session["runs"][0]["runtime_type"] == "direct_llm", f"Expected direct_llm run, got {session['runs'][0]['runtime_type']}")

    print("PASS direct_llm REST chat via llama.cpp")
    print("PASS direct_llm SSE chat via llama.cpp")
    print("PASS direct_llm WebSocket chat via llama.cpp")
    print(f"PROFILE {profile_slug}")
    print(f"EMPLOYEE {employee_email}")
    print(f"CONVERSATION {rest['conversation_id']}")
    print(f"MODEL {args.model}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TestFailure:
        raise SystemExit(1)
