from __future__ import annotations

from datetime import datetime, timezone

from .models import Run, TERMINAL_STATUSES, WorkflowStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InvalidStateTransition(ValueError):
    pass


TRANSITION_RULES: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.pending: {
        WorkflowStatus.awaiting_plan_approval,
        WorkflowStatus.cancelled,
    },
    WorkflowStatus.awaiting_plan_approval: {
        WorkflowStatus.awaiting_step_approval,
        WorkflowStatus.cancelled,
    },
    WorkflowStatus.awaiting_step_approval: {
        WorkflowStatus.running,
        WorkflowStatus.skipped,
        WorkflowStatus.cancelled,
    },
    WorkflowStatus.running: {
        WorkflowStatus.succeeded,
        WorkflowStatus.failed,
        WorkflowStatus.cancelled,
        WorkflowStatus.skipped,
    },
    WorkflowStatus.succeeded: set(),
    WorkflowStatus.failed: set(),
    WorkflowStatus.cancelled: set(),
    WorkflowStatus.skipped: set(),
}


def needs_replan_for_status(status: WorkflowStatus) -> bool:
    return status == WorkflowStatus.failed


def assert_transition(current: WorkflowStatus, next_status: WorkflowStatus) -> None:
    if next_status not in TRANSITION_RULES[current]:
        raise InvalidStateTransition(
            f"Invalid transition: {current.value} -> {next_status.value}"
        )


def apply_transition(
    current: WorkflowStatus,
    next_status: WorkflowStatus,
) -> WorkflowStatus:
    assert_transition(current=current, next_status=next_status)
    return next_status


def transition_run(
    run: Run,
    next_status: WorkflowStatus,
    *,
    failure_reason: str | None = None,
) -> Run:
    run.status = apply_transition(current=run.status, next_status=next_status)
    run.needs_replan = needs_replan_for_status(run.status)

    if run.status == WorkflowStatus.running and run.started_at is None:
        run.started_at = utc_now()

    if run.status == WorkflowStatus.failed:
        run.failure_reason = failure_reason or "step_failed"
    elif run.status in TERMINAL_STATUSES:
        run.failure_reason = None

    if run.status in TERMINAL_STATUSES:
        run.finished_at = utc_now()

    return run
