from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowStatus(str, Enum):
    pending = "pending"
    awaiting_plan_approval = "awaiting_plan_approval"
    awaiting_step_approval = "awaiting_step_approval"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    skipped = "skipped"


class SessionMode(str, Enum):
    normal = "normal"
    dry_run = "dry_run"


TERMINAL_STATUSES: frozenset[WorkflowStatus] = frozenset(
    {
        WorkflowStatus.succeeded,
        WorkflowStatus.failed,
        WorkflowStatus.cancelled,
        WorkflowStatus.skipped,
    }
)


class Session(BaseModel):
    id: str = Field(default_factory=lambda: f"session_{uuid4().hex[:12]}")
    goal: str | None = None
    mode: SessionMode = SessionMode.normal
    status: WorkflowStatus = WorkflowStatus.pending
    plan_version: int | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Step(BaseModel):
    id: str
    title: str
    tool: str
    status: WorkflowStatus = WorkflowStatus.pending


class Plan(BaseModel):
    session_id: str
    version: int = Field(ge=1)
    title: str
    session_goal: str | None = None
    steps: list[Step] = Field(default_factory=list)


class Run(BaseModel):
    id: str = Field(default_factory=lambda: f"run_{uuid4().hex[:12]}")
    session_id: str
    plan_version: int = Field(ge=1)
    step_id: str | None = None
    status: WorkflowStatus = WorkflowStatus.pending
    needs_replan: bool = False
    failure_reason: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: f"artifact_{uuid4().hex[:12]}")
    run_id: str
    path: str
    kind: Literal["file", "log", "report"] = "file"
    created_at: datetime = Field(default_factory=utc_now)


class Approval(BaseModel):
    id: str = Field(default_factory=lambda: f"approval_{uuid4().hex[:12]}")
    subject_type: Literal["plan", "step"]
    subject_id: str
    approved_by: str
    approved: bool = True
    approved_at: datetime = Field(default_factory=utc_now)
