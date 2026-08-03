from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class EvalExpected(BaseModel):
    contains_all: list[str] = Field(default_factory=list, max_length=20)
    contains_any: list[str] = Field(default_factory=list, max_length=20)
    forbidden: list[str] = Field(default_factory=list, max_length=20)
    required_tools: list[str] = Field(default_factory=list, max_length=20)
    require_arabic: bool = False
    max_latency_ms: int | None = Field(default=None, ge=1, le=600000)
    max_cost: float | None = Field(default=None, ge=0, le=10000)

    @model_validator(mode="after")
    def require_assertion(self):
        if not any((self.contains_all, self.contains_any, self.forbidden, self.required_tools, self.require_arabic, self.max_latency_ms, self.max_cost is not None)):
            raise ValueError("Each evaluation case must define at least one assertion")
        return self


class EvalCase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    category: Literal["arabic", "files", "policy", "tools", "general"]
    prompt: str = Field(min_length=1, max_length=20000)
    project_context: str | None = Field(default=None, max_length=50000)
    expected: EvalExpected


class EvalThresholds(BaseModel):
    min_pass_rate: float = Field(default=0.9, ge=0, le=1)
    max_error_rate: float = Field(default=0.1, ge=0, le=1)
    max_latency_regression_pct: float = Field(default=20, ge=0, le=1000)
    max_cost_regression_pct: float = Field(default=20, ge=0, le=1000)


class EvaluationSuiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    profile_id: UUID
    cases: list[EvalCase] = Field(min_length=1, max_length=20)
    thresholds: EvalThresholds = Field(default_factory=EvalThresholds)


class EvaluationRunRequest(BaseModel):
    target_user_id: UUID | None = None
    candidate_label: str | None = Field(default=None, max_length=100)


class FeedbackCreate(BaseModel):
    agent_run_id: UUID
    rating: int = Field(ge=1, le=5)
    outcome: Literal["success", "partial", "failure"]
    tags: list[str] = Field(default_factory=list, max_length=10)
    note: str | None = Field(default=None, max_length=500)
