#!/usr/bin/env python3
"""Collect five-minute production UAT soak evidence without mutating the platform."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = [
    "docker", "compose",
    "-f", str(ROOT / "docker-compose.yml"),
    "-f", str(ROOT / "docker-compose.e2e.yml"),
    "--env-file", str(ROOT / ".env.docker.local"),
]


def run(command: list[str], timeout: int = 30) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[:1000])
    return result.stdout.strip()


def api_request(base_url: str, path: str, token: str = "", body: dict | None = None) -> tuple[int, dict]:
    request = Request(
        base_url.rstrip("/") + path,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        method="GET" if body is None else "POST",
        headers={
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if body is not None else {}),
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"{}")
    except HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * ratio))]


def controller_summary(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "chat_pass": 0, "failures": 0, "latency_ms": {}}
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    chats = [row for row in rows if row.get("type") == "chat_pass"]
    latencies = [float(row.get("latency_ms") or 0) for row in chats]
    completions = [row for row in rows if row.get("type") == "uat_complete"]
    return {
        "exists": True,
        "chat_pass": len(chats),
        "failures": sum(1 for row in completions if row.get("status") == "failed"),
        "completed": any(row.get("status") == "passed" for row in completions),
        "last_event_at": rows[-1].get("at") if rows else None,
        "latency_ms": {
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "max": max(latencies, default=0),
        },
        "quality_sample": [
            {"user": row.get("user"), "content": str(row.get("content") or "")[:120]}
            for row in chats[-4:]
        ],
    }


def docker_stats() -> dict:
    output = run(["docker", "stats", "--no-stream", "--format", "{{json .}}"], timeout=45)
    rows = {}
    for line in output.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = item.get("Name", "")
        if name.startswith("agentsaas-"):
            rows[name] = {
                "cpu": item.get("CPUPerc"),
                "memory": item.get("MemUsage"),
                "memory_percent": item.get("MemPerc"),
                "pids": item.get("PIDs"),
            }
    return rows


def database_stats(started_at: datetime) -> dict:
    start = started_at.replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")
    sql = f"""
      select count(*), count(*) filter (where state='active'),
             count(*) filter (where state='active' and wait_event is not null)
      from pg_stat_activity where datname='fqsaas';
      select count(*) from pg_locks where not granted;
      select coalesce(status,'null'),count(*) from agent_runs where created_at >= timestamp '{start}' group by status order by status;
      select count(*) filter (where status='pending'),count(*) filter (where status='running'),count(*) filter (where status='failed')
      from durable_tasks;
      select verify_audit_log_chain();
    """
    lines = run(COMPOSE + ["exec", "-T", "db", "psql", "-U", "postgres", "-d", "fqsaas", "-At", "-F", "|", "-c", sql]).splitlines()
    connections = [int(item) for item in lines[0].split("|")]
    locks = int(lines[1])
    audit = lines[-1] == "t"
    durable = [int(item) for item in lines[-2].split("|")]
    run_statuses = {}
    for line in lines[2:-2]:
        status, count = line.split("|", 1)
        run_statuses[status] = int(count)
    return {
        "connections": {"total": connections[0], "active": connections[1], "waiting": connections[2]},
        "ungranted_locks": locks,
        "agent_runs": run_statuses,
        "durable_tasks": {"pending": durable[0], "running": durable[1], "failed": durable[2]},
        "audit_chain_valid": audit,
    }


def redis_stats() -> dict:
    info = run(COMPOSE + ["exec", "-T", "redis", "redis-cli", "INFO", "memory"])
    values = {}
    for line in info.splitlines():
        if ":" in line:
            key, value = line.strip().split(":", 1)
            if key in {"used_memory", "used_memory_rss", "mem_fragmentation_ratio"}:
                values[key] = value
    values["celery_queue_depth"] = int(run(COMPOSE + ["exec", "-T", "redis", "redis-cli", "LLEN", "celery"]) or 0)
    return values


def runtime_stats() -> dict:
    count = run(COMPOSE + [
        "exec", "-T", "hermes-runtime", "sh", "-c",
        "find /tmp -maxdepth 1 -type d -name 'hermes-run-*' | wc -l",
    ])
    return {"temporary_run_directories": int(count or 0)}


def service_states() -> dict:
    output = run(COMPOSE + ["ps", "--format", "json"])
    parsed = json.loads(output) if output.startswith("[") else [json.loads(line) for line in output.splitlines() if line]
    return {
        item.get("Service", item.get("Name", "")): {
            "state": item.get("State"),
            "health": item.get("Health"),
        }
        for item in parsed
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-hours", type=float, default=12.25)
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--api-url", default="http://127.0.0.1:8002")
    parser.add_argument("--controller-evidence", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()

    evidence = (ROOT / args.evidence).resolve()
    controller_evidence = (ROOT / args.controller_evidence).resolve()
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.unlink(missing_ok=True)
    started_at = datetime.now(timezone.utc)
    deadline = time.monotonic() + args.duration_hours * 3600
    admin_token = ""
    sample_index = 0

    def record(payload: dict) -> None:
        row = {"at": datetime.now(timezone.utc).isoformat(), **payload}
        with evidence.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps(row, ensure_ascii=False), flush=True)

    record({"type": "soak_monitor_started", "duration_hours": args.duration_hours, "interval_seconds": args.interval_seconds})
    while time.monotonic() < deadline:
        sample_index += 1
        sample_started = time.monotonic()
        controller = controller_summary(controller_evidence)
        if controller.get("failures"):
            record({"type": "soak_monitor_failed", "reason": "controller reported failure", "controller": controller})
            return 1
        try:
            status, online = api_request(args.api_url, "/api/admin/monitoring/online-users", admin_token)
            if status == 401:
                login_status, login = api_request(
                    args.api_url,
                    "/api/auth/login",
                    body={"email": "admin@company.com", "password": "admin123"},
                )
                if login_status != 200:
                    raise RuntimeError(f"admin login returned {login_status}")
                admin_token = login["access_token"]
                status, online = api_request(args.api_url, "/api/admin/monitoring/online-users", admin_token)
            if status != 200:
                raise RuntimeError(f"online users returned {status}")

            snapshot = {
                "type": "soak_snapshot",
                "sample": sample_index,
                "elapsed_minutes": round((datetime.now(timezone.utc) - started_at).total_seconds() / 60, 2),
                "online_users": online.get("online_count", 0),
                "services": service_states(),
                "docker": docker_stats(),
                "database": database_stats(started_at),
                "redis": redis_stats(),
                "runtime": runtime_stats(),
                "controller": {key: value for key, value in controller.items() if key != "quality_sample"},
            }
            if sample_index == 1 or sample_index % 12 == 0:
                snapshot["quality_sample"] = controller.get("quality_sample", [])
            record(snapshot)
            if not snapshot["database"]["audit_chain_valid"]:
                record({"type": "soak_monitor_failed", "reason": "audit chain invalid"})
                return 1
        except Exception as exc:
            record({"type": "soak_sample_error", "sample": sample_index, "error": str(exc)})

        if controller.get("completed"):
            record({"type": "soak_monitor_complete", "status": "passed", "samples": sample_index, "controller": controller})
            return 0
        remaining = args.interval_seconds - (time.monotonic() - sample_started)
        if remaining > 0:
            time.sleep(remaining)

    controller = controller_summary(controller_evidence)
    status = "passed" if controller.get("completed") and not controller.get("failures") else "failed"
    record({"type": "soak_monitor_complete", "status": status, "samples": sample_index, "controller": controller})
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
