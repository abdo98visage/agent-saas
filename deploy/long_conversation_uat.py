#!/usr/bin/env python3
"""Concurrent real-model UAT for long conversation continuity."""

from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError
from urllib.request import Request, urlopen


USERS = [
    ("accounting", "desktop-3a7dd75626@example.com", "Desktop Hermes 3a7dd75626", "MEM-ACCT-581"),
    ("marketing", "desktop-8473674d1e@example.com", "Desktop Hermes 8473674d1e", "MEM-MKT-692"),
    ("hr", "desktop-4d69af9f0b@example.com", "Desktop Hermes 4d69af9f0b", "MEM-HR-703"),
    ("it", "desktop-a8128c7d08@example.com", "Desktop Hermes a8128c7d08", "MEM-IT-814"),
]

print_lock = threading.Lock()


def request(base_url: str, method: str, path: str, body=None, token: str | None = None):
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=180) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} returned {exc.code}: {detail}") from exc


def prepare_quotas(base_url: str, admin_token: str) -> None:
    employees = request(base_url, "GET", "/api/admin/employees", token=admin_token).get("employees", [])
    profiles = request(base_url, "GET", "/api/admin/profiles", token=admin_token).get("profiles", [])
    keys = request(base_url, "GET", "/api/admin/api-keys", token=admin_token).get("api_keys", [])
    emails = {email for _, email, _, _ in USERS}
    profile_names = {profile for _, _, profile, _ in USERS}
    for employee in employees:
        if employee.get("email") in emails:
            request(base_url, "PUT", f"/api/admin/employees/{employee['id']}/quotas", {
                "max_tokens_per_day": 1_000_000_000,
                "max_requests_per_day": 100_000,
            }, admin_token)
    for profile in profiles:
        if profile.get("name") in profile_names:
            request(base_url, "PUT", f"/api/admin/profiles/{profile['id']}", {
                "max_tokens_per_day": 1_000_000_000,
                "max_requests_per_day": 100_000,
            }, admin_token)
    for key in keys:
        if key.get("owner_type") == "profile" and profile_names.intersection(key.get("profile_names") or []):
            request(base_url, "PUT", f"/api/admin/api-keys/{key['id']}", {
                "daily_budget": 1_000_000_000,
            }, admin_token)


def run_user(base_url: str, user: tuple[str, str, str, str], turns: int) -> dict:
    label, email, profile_name, marker = user
    forbidden = {item[3] for item in USERS if item[0] != label}
    login = request(base_url, "POST", "/api/auth/login", {"email": email, "password": "Employee123"})
    token = login["access_token"]
    conversation_id = None
    latencies: list[float] = []

    def chat(message: str):
        nonlocal conversation_id
        started = time.perf_counter()
        response = request(base_url, "POST", "/api/chat/message", {
            "message": message,
            "conversation_id": conversation_id,
            "profile_name": profile_name,
            "agent_template_name": "default",
        }, token)
        latencies.append(time.perf_counter() - started)
        conversation_id = response["conversation_id"]
        return response

    first = chat(f"Remember this private marker for this conversation: {marker}. Reply exactly ACK.")
    if not first.get("content"):
        raise AssertionError(f"{label}: empty first response")
    for turn in range(2, turns):
        response = chat(f"Filler turn {turn}. Reply exactly PING-{turn}.")
        if f"PING-{turn}" not in response.get("content", ""):
            raise AssertionError(f"{label}: wrong filler response at turn {turn}: {response.get('content')!r}")
        if turn in {10, 20}:
            with print_lock:
                print(f"[{label}] turn {turn}/{turns} passed", flush=True)
    final = chat("What private marker did I give you at the beginning? Reply with only that marker.")
    content = final.get("content", "")
    if marker not in content:
        raise AssertionError(f"{label}: forgot {marker}: {content!r}")
    leaked = sorted(value for value in forbidden if value in content)
    if leaked:
        raise AssertionError(f"{label}: leaked markers {leaked}")
    with print_lock:
        print(f"[{label}] turn {turns}/{turns} remembered {marker}", flush=True)
    return {
        "label": label,
        "conversation_id": conversation_id,
        "marker": marker,
        "turns": turns,
        "latency_p50_s": round(statistics.median(latencies), 3),
        "latency_max_s": round(max(latencies), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8002")
    parser.add_argument("--turns", type=int, default=30)
    args = parser.parse_args()
    if args.turns < 3:
        raise SystemExit("--turns must be at least 3")
    admin = request(args.api_url, "POST", "/api/auth/login", {
        "email": "admin@company.com",
        "password": "admin123",
    })
    prepare_quotas(args.api_url, admin["access_token"])
    started = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=len(USERS)) as executor:
        futures = [executor.submit(run_user, args.api_url, user, args.turns) for user in USERS]
        for future in as_completed(futures):
            results.append(future.result())
    print(json.dumps({
        "status": "passed",
        "users": sorted(results, key=lambda item: item["label"]),
        "elapsed_s": round(time.perf_counter() - started, 3),
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
