#!/usr/bin/env python3
"""Safe multi-user REST/WebSocket capacity probe for an on-prem deployment."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from load_test import login, percentile, rest_roundtrip, websocket_roundtrip


DEFAULT_USERS = [
    "accounting,desktop-c5109fb19b@example.com,Desktop Hermes c5109fb19b",
    "marketing,desktop-1e22f1c0eb@example.com,Desktop Hermes 1e22f1c0eb",
    "hr,desktop-edf2a0edfb@example.com,Desktop Hermes edf2a0edfb",
    "it,desktop-ce8b5a0321@example.com,Desktop Hermes ce8b5a0321",
]


@dataclass(frozen=True)
class User:
    label: str
    email: str
    profile: str
    token: str


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def docker_snapshot() -> dict:
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    services = {}
    for line in result.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = item.get("Name", "")
        if name.startswith("agentsaas-"):
            services[name] = {
                "cpu": item.get("CPUPerc"),
                "memory": item.get("MemUsage"),
                "pids": item.get("PIDs"),
            }
    return services


def update_peak(peak: dict, sample: dict) -> None:
    def number(key: str, value: str | None) -> float:
        raw = (value or "0").split()[0]
        try:
            if key == "memory":
                if raw.endswith("GiB"):
                    return float(raw[:-3]) * 1024
                if raw.endswith("MiB"):
                    return float(raw[:-3])
            return float(raw.rstrip("%"))
        except ValueError:
            return 0.0

    for service, values in sample.items():
        current = peak.setdefault(service, dict(values))
        for key in ("cpu", "memory", "pids"):
            if number(key, values.get(key)) > number(key, current.get(key)):
                current[key] = values.get(key)


def parse_user(value: str, password: str, base_url: str) -> User:
    parts = [item.strip() for item in value.split(",", 2)]
    if len(parts) != 3 or not all(parts):
        raise ValueError("--user must be label,email,profile")
    return User(parts[0], parts[1], parts[2], login(base_url, parts[1], password))


def run_level(base_url: str, users: list[User], concurrency: int, timeout_seconds: int, batch_index: int) -> dict:
    barrier = threading.Barrier(concurrency)
    started_at = time.perf_counter()
    successes = []
    failures = []

    def one(index: int) -> dict:
        rotated = index + batch_index
        user = users[index % len(users)]
        transport = "rest" if rotated % 2 == 0 else "websocket"
        marker = f"CAP-{concurrency}-{index}-{int(started_at * 1000)}"
        if rotated % 4 == 2:
            message = ("Capacity context line. " * 180) + f" Reply exactly {marker}."
            workload = "long"
        elif rotated % 4 == 0:
            message = f"Using available enterprise knowledge if relevant, reply exactly {marker}."
            workload = "knowledge"
        else:
            message = f"Reply exactly {marker}."
            workload = "short"
        barrier.wait(timeout=30)
        request_started = time.perf_counter()
        if transport == "rest":
            latency = rest_roundtrip(base_url, user.token, message, user.profile, "default")
        else:
            latency = websocket_roundtrip(base_url, user.token, message, user.profile, "default")
        return {
            "user": user.label,
            "transport": transport,
            "workload": workload,
            "latency_ms": round(latency, 3),
            "started_offset_ms": round((request_started - started_at) * 1000, 3),
        }

    peak = {}
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(one, index) for index in range(concurrency)]
        while not all(future.done() for future in futures):
            update_peak(peak, docker_snapshot())
            time.sleep(0.25)
        for future in as_completed(futures):
            try:
                successes.append(future.result(timeout=timeout_seconds))
            except Exception as exc:
                failures.append(str(exc))

    latencies = [item["latency_ms"] for item in successes]
    by_user = {}
    for user in users:
        values = [item["latency_ms"] for item in successes if item["user"] == user.label]
        by_user[user.label] = {
            "ok": len(values),
            "p95_ms": round(percentile(values, 95), 3) if values else None,
            "max_ms": round(max(values), 3) if values else None,
        }
    return {
        "at": now(),
        "type": "capacity_level",
        "concurrency": concurrency,
        "batch": batch_index + 1,
        "ok": len(successes),
        "failed": len(failures),
        "failures": failures,
        "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 3),
        "p50_ms": round(statistics.median(latencies), 3) if latencies else None,
        "p95_ms": round(percentile(latencies, 95), 3) if latencies else None,
        "max_ms": round(max(latencies), 3) if latencies else None,
        "fairness_ratio": round(max(latencies) / min(latencies), 3) if latencies else None,
        "by_user": by_user,
        "requests": successes,
        "resource_peaks": peak,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8002")
    parser.add_argument("--password", default="Employee123")
    parser.add_argument("--user", action="append", default=[])
    parser.add_argument("--levels", default="4,8,12,16,24,32")
    parser.add_argument("--timeout-seconds", type=int, default=150)
    parser.add_argument("--degradation-factor", type=float, default=1.5)
    parser.add_argument("--evidence", default="uat-evidence/capacity-phase8.jsonl")
    args = parser.parse_args()

    levels = [int(item) for item in args.levels.split(",") if item.strip()]
    if not levels or min(levels) < 1 or max(levels) > 64:
        raise SystemExit("levels must contain integers between 1 and 64")
    users = [parse_user(item, args.password, args.api_url) for item in (args.user or DEFAULT_USERS)]
    if len(users) < 4:
        raise SystemExit("at least four independent users are required")

    evidence = Path(args.evidence)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    baseline_p95 = None
    results = []
    with evidence.open("w", encoding="utf-8") as output:
        start = {"at": now(), "type": "capacity_started", "levels": levels, "users": [u.label for u in users], "resources": docker_snapshot()}
        output.write(json.dumps(start) + "\n")
        output.flush()
        print(json.dumps(start), flush=True)
        for batch_index, level in enumerate(levels):
            result = run_level(args.api_url, users, level, args.timeout_seconds, batch_index)
            results.append(result)
            output.write(json.dumps(result) + "\n")
            output.flush()
            print(json.dumps(result), flush=True)
            if baseline_p95 is None and not result["failed"]:
                baseline_p95 = result["p95_ms"]
            degraded = bool(
                result["failed"]
                or not result["p95_ms"]
                or (baseline_p95 and result["p95_ms"] >= baseline_p95 * args.degradation_factor)
                or result["max_ms"] >= args.timeout_seconds * 1000 * 0.9
            )
            if degraded and level > levels[0]:
                break
            time.sleep(3)
        complete = {
            "at": now(),
            "type": "capacity_complete",
            "status": "passed" if results and not results[0]["failed"] else "failed",
            "tested_levels": [item["concurrency"] for item in results],
            "degradation_at": results[-1]["concurrency"] if len(results) > 1 and (
                results[-1]["failed"] or results[-1]["p95_ms"] >= baseline_p95 * args.degradation_factor
            ) else None,
            "resources": docker_snapshot(),
        }
        output.write(json.dumps(complete) + "\n")
        print(json.dumps(complete), flush=True)
    return 0 if complete["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
