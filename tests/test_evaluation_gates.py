import pytest
from pydantic import ValidationError

from app.main import app
from app.schemas.evaluation import EvalCase, EvalExpected
from app.services.evaluation_service import evaluate_gate, grade_case


def test_quality_case_grades_language_content_tools_latency_and_cost():
    case = {
        "expected": {
            "contains_all": ["سياسة"], "contains_any": ["موافق", "معتمد"],
            "forbidden": ["terminal"], "required_tools": ["query-docs"],
            "require_arabic": True, "max_latency_ms": 1000, "max_cost": 0.1,
        }
    }
    passed, failures = grade_case(case, {
        "content": "هذه سياسة معتمدة", "tools_used": ["query-docs"],
        "latency_ms": 500, "total_cost": 0.01,
    })
    assert passed is True
    assert failures == []


def test_quality_case_reports_only_failed_assertion_names_without_content():
    passed, failures = grade_case({"expected": {"forbidden": ["secret"], "require_arabic": True}}, {
        "content": "secret value", "tools_used": [], "latency_ms": 10, "total_cost": 0,
    })
    assert passed is False
    assert failures == ["forbidden", "require_arabic"]
    assert "secret value" not in str(failures)


def test_regression_gate_blocks_quality_latency_and_cost_degradation():
    passed, failures = evaluate_gate(
        {"pass_rate": 0.8, "error_rate": 0.2, "avg_latency_ms": 130, "avg_cost": 1.3},
        {"min_pass_rate": 0.9, "max_error_rate": 0.1, "max_latency_regression_pct": 20, "max_cost_regression_pct": 20},
        {"avg_latency_ms": 100, "avg_cost": 1.0},
    )
    assert passed is False
    assert set(failures) == {"min_pass_rate", "max_error_rate", "max_latency_regression_pct", "max_cost_regression_pct"}


def test_eval_case_rejects_a_case_without_an_objective_assertion():
    with pytest.raises(ValidationError):
        EvalCase(name="empty", category="general", prompt="test", expected=EvalExpected())


def test_evaluation_and_feedback_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert "/api/admin/evals/suites" in paths
    assert "/api/admin/evals/suites/{suite_id}/run" in paths
    assert "/api/admin/evals/runs/{run_id}/promote-baseline" in paths
    assert "/api/admin/evals/canary/{profile_id}" in paths
    assert "/api/evals/feedback" in paths
