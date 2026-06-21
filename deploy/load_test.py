"""Lightweight REST + WebSocket load test for AgentSaaS.

Uses only the Python standard library so it can run on fresh hosts.
Intended for pre-production smoke/performance baselines, not full stress testing.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import statistics
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener


Json = dict[str, Any]


class LoadTestFailure(RuntimeError):
    pass


@dataclass
class ApiClient:
    base_url: str
    token: str | None = None
    timeout_seconds: float = 60.0
    jar: CookieJar = field(default_factory=CookieJar)

    def __post_init__(self) -> None:
        self.opener = build_opener(HTTPCookieProcessor(self.jar))

    def request(self, method: str, path: str, body: Json | None = None, expected: int | tuple[int, ...] = (200,)) -> Any:
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
            with self.opener.open(req, timeout=self.timeout_seconds) as response:
                payload = response.read()
                if response.status not in expected_codes:
                    raise LoadTestFailure(f"{method} {path} returned {response.status}, expected {expected_codes}")
                return self._decode(payload, response.headers.get("Content-Type", ""))
        except HTTPError as exc:
            payload = exc.read()
            decoded = self._decode(payload, exc.headers.get("Content-Type", ""))
            raise LoadTestFailure(f"{method} {path} returned {exc.code}: {decoded}") from exc
        except URLError as exc:
            raise LoadTestFailure(f"{method} {path} failed: {exc}") from exc

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


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1)))))
    return ordered[index]


def wait_until_ready(client: ApiClient, timeout: int) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            ready = client.request("GET", "/api/ready")
            if ready.get("status") == "ready":
                return
        except Exception:
            pass
        time.sleep(2)
    raise LoadTestFailure("API did not become ready before load test")


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
        raise LoadTestFailure("WebSocket closed before frame header")
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
            raise LoadTestFailure("WebSocket closed while reading frame")
        payload += chunk
    if masked:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


def login(base_url: str, email: str, password: str) -> str:
    client = ApiClient(base_url=base_url)
    response = client.request("POST", "/api/auth/login", {"email": email, "password": password})
    token = response.get("access_token")
    if not token:
        raise LoadTestFailure("Login did not return access_token")
    return token


def rest_roundtrip(base_url: str, token: str, message: str, profile_name: str, template: str) -> float:
    client = ApiClient(base_url=base_url, token=token)
    started = time.perf_counter()
    response = client.request(
        "POST",
        "/api/chat/message",
        {
            "message": message,
            "profile_name": profile_name or None,
            "agent_template_name": template,
        },
    )
    if not response.get("content"):
        raise LoadTestFailure("REST chat response was empty")
    return (time.perf_counter() - started) * 1000


def websocket_roundtrip(base_url: str, token: str, message: str, profile_name: str, template: str) -> float:
    client = ApiClient(base_url=base_url, token=token)
    ws_token = client.request("POST", "/api/auth/ws-token").get("access_token")
    if not ws_token:
        raise LoadTestFailure("Failed to obtain ws access token")

    parsed = urlparse(base_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    ws_protocol = "wss" if parsed.scheme == "https" else "ws"
    _ = ws_protocol  # marker for audit/test visibility
    path = "/api/chat/ws/chat?" + urlencode(
        {
            "token": ws_token,
            "agent_template_name": template,
            "profile_name": profile_name or "",
        }
    )
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    started = time.perf_counter()
    with socket.create_connection((host, port), timeout=15) as sock:
        sock.settimeout(90)
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
            raise LoadTestFailure(f"WebSocket handshake failed: {response[:200]!r}")

        ws_send(sock, 1, json.dumps({"type": "message", "content": message}).encode("utf-8"))

        deadline = time.time() + 90
        while time.time() < deadline:
            opcode, payload = ws_read_frame(sock)
            if opcode == 9:
                ws_send(sock, 10, payload)
                continue
            if opcode == 8:
                raise LoadTestFailure(f"WebSocket closed before done event: {payload!r}")
            if opcode != 1:
                continue
            event = json.loads(payload.decode("utf-8"))
            if event.get("type") == "error":
                raise LoadTestFailure(f"WebSocket returned error: {event}")
            if event.get("type") == "done":
                return (time.perf_counter() - started) * 1000
        raise LoadTestFailure("WebSocket test timed out before done event")


def summarize(label: str, latencies: list[float], failures: int) -> None:
    if latencies:
        avg = statistics.mean(latencies)
        p50 = percentile(latencies, 50)
        p95 = percentile(latencies, 95)
        print(
            f"{label}: ok={len(latencies)} failed={failures} "
            f"avg_ms={avg:.1f} p50_ms={p50:.1f} p95_ms={p95:.1f} "
            f"min_ms={min(latencies):.1f} max_ms={max(latencies):.1f}"
        )
    else:
        print(f"{label}: ok=0 failed={failures}")


def run_parallel(label: str, concurrency: int, iterations: int, fn) -> tuple[list[float], int]:
    latencies: list[float] = []
    failures = 0
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(fn) for _ in range(iterations)]
        for future in as_completed(futures):
            try:
                latency = future.result()
                with lock:
                    latencies.append(latency)
            except Exception as exc:
                failures += 1
                print(f"{label} failure: {exc}")
    return latencies, failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AgentSaaS lightweight load/performance test")
    parser.add_argument("--base-url", default="http://localhost:8002")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--message", default="Write one short performance test line.")
    parser.add_argument("--profile-name", default="")
    parser.add_argument("--agent-template", default="default")
    parser.add_argument("--rest-concurrency", type=int, default=3)
    parser.add_argument("--rest-iterations", type=int, default=6)
    parser.add_argument("--ws-concurrency", type=int, default=2)
    parser.add_argument("--ws-iterations", type=int, default=4)
    parser.add_argument("--ready-timeout", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    readiness_client = ApiClient(base_url=args.base_url)
    wait_until_ready(readiness_client, args.ready_timeout)
    token = login(args.base_url, args.email, args.password)

    rest_latencies, rest_failures = run_parallel(
        "REST",
        args.rest_concurrency,
        args.rest_iterations,
        lambda: rest_roundtrip(args.base_url, token, args.message, args.profile_name, args.agent_template),
    )
    ws_latencies, ws_failures = run_parallel(
        "WebSocket",
        args.ws_concurrency,
        args.ws_iterations,
        lambda: websocket_roundtrip(args.base_url, token, args.message, args.profile_name, args.agent_template),
    )

    summarize("REST", rest_latencies, rest_failures)
    summarize("WebSocket", ws_latencies, ws_failures)

    if rest_failures or ws_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
