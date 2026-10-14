from datetime import UTC, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.dora import (
    compute_change_failure_rate,
    compute_deployment_frequency,
    compute_lead_time_for_changes,
    compute_mttr_hours,
)


def test_compute_deployment_frequency_counts_successful_push_runs_only() -> None:
    week_labels = ["2026-W40", "2026-W41"]
    runs = [
        {"event": "push", "conclusion": "success", "updated_at": "2026-10-01T10:00:00Z", "head_sha": "a"},
        {"event": "push", "conclusion": "failure", "updated_at": "2026-10-01T11:00:00Z", "head_sha": "b"},
        {"event": "workflow_dispatch", "conclusion": "success", "updated_at": "2026-10-02T11:00:00Z", "head_sha": "c"},
        {"event": "push", "conclusion": "success", "updated_at": "2026-10-08T09:00:00Z", "head_sha": "d"},
    ]

    frequency, successful = compute_deployment_frequency(
        runs,
        week_labels,
        datetime(2026, 9, 28, tzinfo=UTC),
    )

    assert frequency == {"2026-W40": 1, "2026-W41": 1}
    assert [run["head_sha"] for run in successful] == ["a", "d"]


def test_compute_lead_time_for_changes_returns_weekly_median_hours() -> None:
    week_labels = ["2026-W41"]
    merged_prs = [{"number": 1, "merge_commit_sha": "sha-1"}, {"number": 2, "merge_commit_sha": "sha-2"}]
    first_commit_dates = {
        1: datetime(2026, 10, 4, 0, 0, tzinfo=UTC),
        2: datetime(2026, 10, 5, 6, 0, tzinfo=UTC),
    }
    successful_deploy_runs = [
        {"head_sha": "sha-1", "updated_at": "2026-10-07T00:00:00Z"},
        {"head_sha": "sha-2", "updated_at": "2026-10-08T06:00:00Z"},
    ]

    lead_time = compute_lead_time_for_changes(merged_prs, first_commit_dates, successful_deploy_runs, week_labels)

    assert lead_time["2026-W41"] == 72.0


def test_compute_change_failure_rate_handles_zero_deployments_and_zero_incidents() -> None:
    week_labels = ["2026-W40", "2026-W41"]
    incident_issues = [{"created_at": "2026-10-01T12:00:00Z"}]
    deployment_frequency = {"2026-W40": 2, "2026-W41": 0}

    rates = compute_change_failure_rate(incident_issues, deployment_frequency, week_labels)

    assert rates["2026-W40"] == 0.5
    assert rates["2026-W41"] is None


def test_compute_mttr_hours_returns_average_and_none_for_empty_week() -> None:
    week_labels = ["2026-W40", "2026-W41"]
    incident_issues = [
        {"created_at": "2026-10-01T00:00:00Z", "closed_at": "2026-10-01T02:00:00Z"},
        {"created_at": "2026-10-01T00:00:00Z", "closed_at": "2026-10-01T04:00:00Z"},
    ]

    mttr = compute_mttr_hours(incident_issues, week_labels)

    assert mttr["2026-W40"] == 3.0
    assert mttr["2026-W41"] is None
