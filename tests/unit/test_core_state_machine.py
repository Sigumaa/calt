import pytest
from pydantic import ValidationError

from calt.core import (
    Approval,
    Artifact,
    InvalidStateTransition,
    Plan,
    Run,
    Session,
    Step,
    WorkflowStatus,
    needs_replan_for_status,
    transition_run,
)


def test_models_minimum_instances_are_created() -> None:
    session = Session(goal="mvp")
    step = Step(id="step_001", title="Read file", tool="read_file")
    plan = Plan(session_id=session.id, version=1, title="Plan A", steps=[step])
    run = Run(session_id=session.id, plan_version=plan.version, step_id=step.id)
    artifact = Artifact(run_id=run.id, path="artifacts/out.txt")
    approval = Approval(subject_type="plan", subject_id="1", approved_by="user_1")

    assert session.status == WorkflowStatus.pending
    assert plan.steps[0].id == "step_001"
    assert run.status == WorkflowStatus.pending
    assert artifact.kind == "file"
    assert approval.approved is True


def test_plan_version_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Plan(session_id="session_1", version=0, title="invalid")


def test_transition_run_happy_path() -> None:
    run = Run(session_id="session_1", plan_version=1, step_id="step_001")

    transition_run(run, WorkflowStatus.awaiting_plan_approval)
    transition_run(run, WorkflowStatus.awaiting_step_approval)
    transition_run(run, WorkflowStatus.running)
    transition_run(run, WorkflowStatus.succeeded)

    assert run.status == WorkflowStatus.succeeded
    assert run.needs_replan is False
    assert run.started_at is not None
    assert run.finished_at is not None


def test_transition_run_failed_sets_needs_replan() -> None:
    run = Run(session_id="session_1", plan_version=1)

    transition_run(run, WorkflowStatus.awaiting_plan_approval)
    transition_run(run, WorkflowStatus.awaiting_step_approval)
    transition_run(run, WorkflowStatus.running)
    transition_run(run, WorkflowStatus.failed, failure_reason="tool_timeout")

    assert run.status == WorkflowStatus.failed
    assert run.needs_replan is True
    assert run.failure_reason == "tool_timeout"
    assert needs_replan_for_status(run.status) is True


def test_invalid_transition_raises_error() -> None:
    run = Run(session_id="session_1", plan_version=1)
    with pytest.raises(InvalidStateTransition):
        transition_run(run, WorkflowStatus.running)


def test_terminal_state_cannot_transition() -> None:
    run = Run(session_id="session_1", plan_version=1)
    transition_run(run, WorkflowStatus.awaiting_plan_approval)
    transition_run(run, WorkflowStatus.awaiting_step_approval)
    transition_run(run, WorkflowStatus.running)
    transition_run(run, WorkflowStatus.succeeded)

    with pytest.raises(InvalidStateTransition):
        transition_run(run, WorkflowStatus.running)
