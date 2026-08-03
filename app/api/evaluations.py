import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_admin_user, get_current_user
from app.core.db import get_db
from app.models.agent_run import AgentRun
from app.models.evaluation import AgentFeedback, EvaluationRun, EvaluationSuite
from app.models.profile import Profile
from app.models.user import User
from app.schemas.evaluation import EvaluationRunRequest, EvaluationSuiteCreate, FeedbackCreate
from app.services.audit_service import log_audit_event
from app.services.evaluation_service import run_evaluation


router = APIRouter()


def _suite_response(suite: EvaluationSuite) -> dict:
    return {
        "id": str(suite.id), "name": suite.name, "profile_id": str(suite.profile_id),
        "version": suite.version, "cases": suite.cases, "thresholds": suite.thresholds,
        "baseline_run_id": str(suite.baseline_run_id) if suite.baseline_run_id else None,
        "is_active": suite.is_active,
    }


def _run_response(run: EvaluationRun) -> dict:
    return {
        "id": str(run.id), "suite_id": str(run.suite_id),
        "profile_id": str(run.profile_id) if run.profile_id else None,
        "profile_version": run.profile_version, "status": run.status,
        "candidate_label": run.candidate_label, "metrics": run.metrics,
        "case_results": run.case_results, "is_baseline": run.is_baseline,
        "started_at": run.started_at, "completed_at": run.completed_at,
    }


@router.post("/admin/evals/suites", status_code=status.HTTP_201_CREATED)
async def create_suite(
    request: EvaluationSuiteCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    if not await db.get(Profile, request.profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    suite = EvaluationSuite(
        name=request.name, profile_id=request.profile_id,
        cases=[case.model_dump() for case in request.cases], thresholds=request.thresholds.model_dump(),
    )
    db.add(suite)
    await db.flush()
    await log_audit_event(db, admin.id, "evaluation_suite_created", {"case_count": len(suite.cases)}, event_category="quality", subject_type="evaluation_suite", subject_id=str(suite.id))
    return _suite_response(suite)


@router.get("/admin/evals/suites")
async def list_suites(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    suites = (await db.execute(select(EvaluationSuite).order_by(EvaluationSuite.created_at.desc()))).scalars().all()
    return {"suites": [_suite_response(suite) for suite in suites], "count": len(suites)}


@router.post("/admin/evals/suites/{suite_id}/run")
async def run_suite(
    suite_id: UUID,
    request: EvaluationRunRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    suite = await db.get(EvaluationSuite, suite_id)
    if not suite or not suite.is_active:
        raise HTTPException(status_code=404, detail="Evaluation suite not found")
    try:
        run = await run_evaluation(db, suite, admin.id, request.target_user_id, request.candidate_label)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await log_audit_event(db, admin.id, "evaluation_run_completed", {"status": run.status, "metrics": run.metrics}, event_category="quality", subject_type="evaluation_run", subject_id=str(run.id))
    return _run_response(run)


@router.get("/admin/evals/runs/{run_id}")
async def get_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    run = await db.get(EvaluationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return _run_response(run)


@router.post("/admin/evals/runs/{run_id}/promote-baseline")
async def promote_baseline(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    run = await db.get(EvaluationRun, run_id)
    if not run or run.status != "passed":
        raise HTTPException(status_code=409, detail="Only a passing evaluation can become the baseline")
    suite = await db.get(EvaluationSuite, run.suite_id)
    prior = (await db.execute(select(EvaluationRun).where(EvaluationRun.suite_id == suite.id, EvaluationRun.is_baseline.is_(True)))).scalars().all()
    for item in prior:
        item.is_baseline = False
    run.is_baseline = True
    suite.baseline_run_id = run.id
    await log_audit_event(db, admin.id, "evaluation_baseline_promoted", event_category="quality", subject_type="evaluation_run", subject_id=str(run.id))
    return {"status": "promoted", "run_id": str(run.id), "suite_id": str(suite.id)}


@router.post("/evals/feedback", status_code=status.HTTP_201_CREATED)
async def create_feedback(
    request: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = await db.get(AgentRun, request.agent_run_id)
    if not run or (user.role != "admin" and run.user_id != user.id):
        raise HTTPException(status_code=404, detail="Agent run not found")
    existing = (await db.execute(select(AgentFeedback).where(AgentFeedback.user_id == user.id, AgentFeedback.agent_run_id == run.id))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Feedback already submitted for this run")
    feedback = AgentFeedback(
        user_id=user.id, agent_run_id=run.id, rating=request.rating, outcome=request.outcome,
        tags=request.tags, note_hash=hashlib.sha256(request.note.encode()).hexdigest() if request.note else None,
    )
    db.add(feedback)
    await db.flush()
    await log_audit_event(db, user.id, "evaluation_feedback_submitted", {"rating": request.rating, "outcome": request.outcome, "tags": request.tags}, event_category="quality", subject_type="agent_run", subject_id=str(run.id), run_id=run.id)
    return {"id": str(feedback.id), "status": "recorded"}


@router.get("/admin/evals/canary/{profile_id}")
async def canary_gate(
    profile_id: UUID,
    candidate_version: int = Query(ge=1),
    min_samples: int = Query(default=5, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_user),
):
    query = text("""
        SELECT ar.profile_version, count(*) AS samples,
          avg(CASE WHEN ar.status IN ('completed','succeeded') THEN 0 ELSE 1 END) AS error_rate,
          avg(coalesce(ar.latency_ms, 0)) AS avg_latency_ms,
          avg(coalesce(ar.total_cost, 0)) AS avg_cost,
          avg(af.rating) AS avg_rating
        FROM agent_runs ar LEFT JOIN agent_feedback af ON af.agent_run_id = ar.id
        WHERE ar.profile_id = :profile_id AND ar.profile_version IN (:candidate, :baseline)
        GROUP BY ar.profile_version
    """)
    rows = (await db.execute(query, {"profile_id": profile_id, "candidate": candidate_version, "baseline": candidate_version - 1})).mappings().all()
    by_version = {row["profile_version"]: dict(row) for row in rows}
    candidate = by_version.get(candidate_version)
    baseline = by_version.get(candidate_version - 1)
    if not candidate or int(candidate["samples"]) < min_samples or not baseline:
        return {"status": "insufficient_data", "rollback_required": False, "candidate": candidate, "baseline": baseline}
    reasons = []
    if float(candidate["error_rate"] or 0) > float(baseline["error_rate"] or 0) + 0.05:
        reasons.append("error_rate")
    if float(baseline["avg_latency_ms"] or 0) > 0 and float(candidate["avg_latency_ms"] or 0) > float(baseline["avg_latency_ms"]) * 1.2:
        reasons.append("latency")
    if candidate["avg_rating"] is not None and baseline["avg_rating"] is not None and float(candidate["avg_rating"]) < float(baseline["avg_rating"]) - 0.5:
        reasons.append("quality")
    return {"status": "rollback_required" if reasons else "passed", "rollback_required": bool(reasons), "reasons": reasons, "candidate": candidate, "baseline": baseline}
