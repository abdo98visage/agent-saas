import hashlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import EvaluationRun, EvaluationSuite
from app.models.profile import Profile
from app.models.profile_user import ProfileUser
from app.models.user import User
from app.services.agent_service import AgentService


def grade_case(case: dict, response: dict) -> tuple[bool, list[str]]:
    expected = case.get("expected") or {}
    content = str(response.get("content") or "")
    normalized = content.casefold()
    failures: list[str] = []
    all_terms = [str(item).casefold() for item in expected.get("contains_all") or []]
    any_terms = [str(item).casefold() for item in expected.get("contains_any") or []]
    forbidden = [str(item).casefold() for item in expected.get("forbidden") or []]
    used_tools = {str(item).casefold() for item in response.get("tools_used") or []}
    if all_terms and not all(term in normalized for term in all_terms):
        failures.append("contains_all")
    if any_terms and not any(term in normalized for term in any_terms):
        failures.append("contains_any")
    if forbidden and any(term in normalized for term in forbidden):
        failures.append("forbidden")
    if expected.get("require_arabic") and not any("\u0600" <= char <= "\u06ff" for char in content):
        failures.append("require_arabic")
    required_tools = {str(item).casefold() for item in expected.get("required_tools") or []}
    if required_tools and not required_tools.issubset(used_tools):
        failures.append("required_tools")
    if expected.get("max_latency_ms") is not None and int(response.get("latency_ms") or 0) > int(expected["max_latency_ms"]):
        failures.append("max_latency_ms")
    if expected.get("max_cost") is not None and float(response.get("total_cost") or 0) > float(expected["max_cost"]):
        failures.append("max_cost")
    return not failures, failures


def evaluate_gate(metrics: dict, thresholds: dict, baseline: dict | None = None) -> tuple[bool, list[str]]:
    failures = []
    if metrics["pass_rate"] < float(thresholds.get("min_pass_rate", 0.9)):
        failures.append("min_pass_rate")
    if metrics["error_rate"] > float(thresholds.get("max_error_rate", 0.1)):
        failures.append("max_error_rate")
    if baseline:
        for metric, threshold_name in (("avg_latency_ms", "max_latency_regression_pct"), ("avg_cost", "max_cost_regression_pct")):
            old = float(baseline.get(metric) or 0)
            new = float(metrics.get(metric) or 0)
            if old > 0 and ((new - old) / old * 100) > float(thresholds.get(threshold_name, 20)):
                failures.append(threshold_name)
    return not failures, failures


async def run_evaluation(
    db: AsyncSession,
    suite: EvaluationSuite,
    triggered_by_user_id,
    target_user_id=None,
    candidate_label: str | None = None,
) -> EvaluationRun:
    profile = await db.get(Profile, suite.profile_id)
    if not profile or not profile.is_active:
        raise ValueError("Evaluation profile is unavailable")
    assignment_query = select(ProfileUser).join(User, User.id == ProfileUser.user_id).where(
        ProfileUser.profile_id == profile.id, User.is_active.is_(True), User.is_activated.is_(True)
    )
    if target_user_id:
        assignment_query = assignment_query.where(ProfileUser.user_id == target_user_id)
    assignment = (await db.execute(assignment_query.order_by(ProfileUser.priority.desc()).limit(1))).scalar_one_or_none()
    if not assignment:
        raise ValueError("No active employee is assigned to the evaluation profile")

    run = EvaluationRun(
        suite_id=suite.id, profile_id=profile.id, profile_version=profile.version,
        triggered_by_user_id=triggered_by_user_id, candidate_label=candidate_label, status="running",
    )
    db.add(run)
    await db.flush()
    service = AgentService()
    results = []
    latencies = []
    costs = []
    errors = 0
    for index, case in enumerate(suite.cases):
        try:
            response = await service.run_agent(
                db=db, user_id=str(assignment.user_id), conversation_id=None,
                user_message=case["prompt"], project_context=case.get("project_context"),
                profile_name=profile.name,
            )
            passed, failures = grade_case(case, response)
            latencies.append(int(response.get("latency_ms") or 0))
            costs.append(float(response.get("total_cost") or 0))
            results.append({
                "index": index, "name": case["name"], "category": case["category"],
                "passed": passed, "failures": failures,
                "output_sha256": hashlib.sha256(str(response.get("content") or "").encode()).hexdigest(),
                "latency_ms": latencies[-1], "cost": costs[-1],
            })
        except Exception as exc:
            errors += 1
            results.append({
                "index": index, "name": case["name"], "category": case["category"],
                "passed": False, "failures": ["runtime_error"], "error_type": exc.__class__.__name__,
            })
    total = len(results)
    passed_count = sum(1 for item in results if item["passed"])
    metrics = {
        "case_count": total, "passed_count": passed_count,
        "pass_rate": passed_count / total if total else 0,
        "error_rate": errors / total if total else 0,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
        "avg_cost": sum(costs) / len(costs) if costs else 0,
        "total_cost": sum(costs),
    }
    baseline_metrics = None
    if suite.baseline_run_id:
        baseline_run = await db.get(EvaluationRun, suite.baseline_run_id)
        baseline_metrics = baseline_run.metrics if baseline_run else None
    passed, gate_failures = evaluate_gate(metrics, suite.thresholds or {}, baseline_metrics)
    metrics["gate_failures"] = gate_failures
    run.metrics = metrics
    run.case_results = results
    run.status = "passed" if passed else "failed"
    run.completed_at = datetime.utcnow()
    await db.flush()
    return run
