from __future__ import annotations

import json
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import requests

DORA_THRESHOLDS: dict[str, dict[str, Any]] = {
    "deployment_frequency": {
        "elite_min_per_week": 7.0,
        "high_min_per_week": 1.0,
        "medium_min_per_week": 0.25,
    },
    "lead_time_hours": {
        "elite_max_hours": 24.0,
        "high_max_hours": 24.0 * 7,
        "medium_max_hours": 24.0 * 30,
    },
    "change_failure_rate": {
        "elite_max_ratio": 0.15,
        "high_max_ratio": 0.30,
        "medium_max_ratio": 0.45,
    },
    "mttr_hours": {
        "elite_max_hours": 24.0,
        "high_max_hours": 24.0 * 7,
        "medium_max_hours": 24.0 * 30,
    },
}


@dataclass
class GitHubApi:
    repository: str
    token: str

    def __post_init__(self) -> None:
        self.base_url = f"https://api.github.com/repos/{self.repository}"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self.token,
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _request(self, url: str, params: dict[str, Any] | None = None) -> requests.Response:
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response

    def paginate(self, url: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        next_url = url
        next_params = dict(params or {})
        next_params.setdefault("per_page", 100)

        while next_url:
            response = self._request(next_url, next_params)
            payload = response.json()
            if isinstance(payload, dict):
                items = payload.get("workflow_runs") or payload.get("items")
                if not isinstance(items, list):
                    items = []
            else:
                items = payload
            collected.extend(item for item in items if isinstance(item, dict))

            link_header = response.headers.get("Link", "")
            next_url = None
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
                    break
            next_params = None
        return collected

    def fetch_deploy_workflow_runs(self) -> list[dict[str, Any]]:
        return self.paginate(f"{self.base_url}/actions/workflows/deploy.yml/runs", {"status": "completed"})

    def fetch_merged_pull_requests(self) -> list[dict[str, Any]]:
        pulls = self.paginate(
            f"{self.base_url}/pulls",
            {"state": "closed", "base": "main", "sort": "updated", "direction": "desc"},
        )
        return [pr for pr in pulls if pr.get("merged_at") and pr.get("merge_commit_sha")]

    def fetch_pr_first_commit_author_date(self, pull_number: int) -> datetime | None:
        commits = self.paginate(f"{self.base_url}/pulls/{pull_number}/commits")
        if not commits:
            return None
        authored = commits[0].get("commit", {}).get("author", {}).get("date")
        return parse_github_datetime(authored) if authored else None

    def fetch_incident_issues(self) -> list[dict[str, Any]]:
        issues = self.paginate(f"{self.base_url}/issues", {"state": "all", "labels": "incident", "sort": "created"})
        return [issue for issue in issues if "pull_request" not in issue]


def parse_github_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def iso_week_label(value: datetime) -> str:
    year, week, _ = value.isocalendar()
    return f"{year}-W{week:02d}"


def recent_week_starts(now: datetime, count: int = 12) -> list[datetime]:
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return [monday - timedelta(weeks=index) for index in range(count - 1, -1, -1)]


def compute_deployment_frequency(
    workflow_runs: list[dict[str, Any]],
    week_labels: list[str],
    week_start_min: datetime,
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    frequency = {week: 0 for week in week_labels}
    successful_push_runs: list[dict[str, Any]] = []

    for run in workflow_runs:
        if run.get("event") != "push" or run.get("conclusion") != "success":
            continue
        updated_at = parse_github_datetime(run.get("updated_at"))
        if not updated_at or updated_at < week_start_min:
            continue
        week = iso_week_label(updated_at)
        if week in frequency:
            frequency[week] += 1
            successful_push_runs.append(run)

    return frequency, successful_push_runs


def compute_lead_time_for_changes(
    merged_pull_requests: list[dict[str, Any]],
    pr_first_commit_dates: dict[int, datetime],
    successful_deploy_runs: list[dict[str, Any]],
    week_labels: list[str],
) -> dict[str, float | None]:
    lead_times_by_week: dict[str, list[float]] = defaultdict(list)

    deployment_by_sha: dict[str, datetime] = {}
    for run in successful_deploy_runs:
        sha = run.get("head_sha")
        deployed_at = parse_github_datetime(run.get("updated_at"))
        if not sha or not deployed_at:
            continue
        current = deployment_by_sha.get(sha)
        if current is None or deployed_at < current:
            deployment_by_sha[sha] = deployed_at

    for pr in merged_pull_requests:
        pull_number = pr.get("number")
        merge_sha = pr.get("merge_commit_sha")
        if not isinstance(pull_number, int) or not merge_sha:
            continue
        first_commit_at = pr_first_commit_dates.get(pull_number)
        deployed_at = deployment_by_sha.get(merge_sha)
        if not first_commit_at or not deployed_at or deployed_at < first_commit_at:
            continue
        week = iso_week_label(deployed_at)
        if week not in week_labels:
            continue
        lead_hours = (deployed_at - first_commit_at).total_seconds() / 3600.0
        lead_times_by_week[week].append(lead_hours)

    result: dict[str, float | None] = {}
    for week in week_labels:
        values = lead_times_by_week.get(week, [])
        result[week] = statistics.median(values) if values else None
    return result


def compute_change_failure_rate(
    incident_issues: list[dict[str, Any]],
    deployment_frequency: dict[str, int],
    week_labels: list[str],
) -> dict[str, float | None]:
    incidents_created_by_week = {week: 0 for week in week_labels}
    for issue in incident_issues:
        created_at = parse_github_datetime(issue.get("created_at"))
        if not created_at:
            continue
        week = iso_week_label(created_at)
        if week in incidents_created_by_week:
            incidents_created_by_week[week] += 1

    result: dict[str, float | None] = {}
    for week in week_labels:
        deployments = deployment_frequency.get(week, 0)
        if deployments == 0:
            result[week] = None
            continue
        result[week] = incidents_created_by_week[week] / deployments
    return result


def compute_mttr_hours(incident_issues: list[dict[str, Any]], week_labels: list[str]) -> dict[str, float | None]:
    mttr_by_week: dict[str, list[float]] = defaultdict(list)
    for issue in incident_issues:
        created_at = parse_github_datetime(issue.get("created_at"))
        closed_at = parse_github_datetime(issue.get("closed_at"))
        if not created_at or not closed_at or closed_at < created_at:
            continue
        week = iso_week_label(closed_at)
        if week not in week_labels:
            continue
        mttr_by_week[week].append((closed_at - created_at).total_seconds() / 3600.0)

    result: dict[str, float | None] = {}
    for week in week_labels:
        values = mttr_by_week.get(week, [])
        result[week] = (sum(values) / len(values)) if values else None
    return result


def grade_deployment_frequency(value: float | int | None) -> str:
    if value is None:
        return "N/A"
    thresholds = DORA_THRESHOLDS["deployment_frequency"]
    if value >= thresholds["elite_min_per_week"]:
        return "Elite"
    if value >= thresholds["high_min_per_week"]:
        return "High"
    if value >= thresholds["medium_min_per_week"]:
        return "Medium"
    return "Low"


def grade_lower_is_better(value: float | None, thresholds: dict[str, float]) -> str:
    if value is None:
        return "N/A"
    if "elite_max_hours" in thresholds:
        elite = thresholds["elite_max_hours"]
        high = thresholds["high_max_hours"]
        medium = thresholds["medium_max_hours"]
    else:
        elite = thresholds["elite_max_ratio"]
        high = thresholds["high_max_ratio"]
        medium = thresholds["medium_max_ratio"]

    if value <= elite:
        return "Elite"
    if value <= high:
        return "High"
    if value <= medium:
        return "Medium"
    return "Low"


def grade_lead_time(value: float | None) -> str:
    return grade_lower_is_better(value, DORA_THRESHOLDS["lead_time_hours"])


def grade_change_failure_rate(value: float | None) -> str:
    return grade_lower_is_better(value, DORA_THRESHOLDS["change_failure_rate"])


def grade_mttr(value: float | None) -> str:
    return grade_lower_is_better(value, DORA_THRESHOLDS["mttr_hours"])


def build_metric_rows(
    week_labels: list[str],
    deployment_frequency: dict[str, int],
    lead_time_hours: dict[str, float | None],
    change_failure_rate: dict[str, float | None],
    mttr_hours: dict[str, float | None],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for week in week_labels:
        rows.append(
            {
                "week": week,
                "deployment_frequency": deployment_frequency.get(week, 0),
                "lead_time_hours": _rounded_or_none(lead_time_hours.get(week)),
                "change_failure_rate": _rounded_or_none(change_failure_rate.get(week)),
                "mttr_hours": _rounded_or_none(mttr_hours.get(week)),
            }
        )
    return rows


def _rounded_or_none(value: float | None) -> float | None:
    return round(value, 2) if isinstance(value, float) else None


def _format_metric(value: float | int | None, unit: str = "") -> str:
    if value is None:
        return "N/A"
    suffix = f" {unit}" if unit else ""
    if isinstance(value, int):
        return f"{value}{suffix}"
    return f"{value:.2f}{suffix}"


def _delta(current: float | int | None, previous: float | int | None, unit: str = "") -> str:
    if current is None or previous is None:
        return "N/A"
    diff = current - previous
    sign = "+" if diff >= 0 else ""
    suffix = f" {unit}" if unit else ""
    if isinstance(diff, float):
        return f"{sign}{diff:.2f}{suffix}"
    return f"{sign}{diff}{suffix}"


def write_weekly_report(rows: list[dict[str, Any]], output_dir: Path) -> Path:
    current = rows[-1]
    previous = rows[-2] if len(rows) > 1 else current
    week = current["week"]

    path = output_dir / f"weekly-{week}.md"
    path.write_text(
        "\n".join(
            [
                f"# DORA Weekly Report ({week})",
                "",
                "## This Week",
                f"- Deployment Frequency: {_format_metric(current['deployment_frequency'])} ({grade_deployment_frequency(current['deployment_frequency'])})",
                f"- Lead Time for Changes: {_format_metric(current['lead_time_hours'], 'hours')} ({grade_lead_time(current['lead_time_hours'])})",
                f"- Change Failure Rate: {_format_metric(current['change_failure_rate'])} ({grade_change_failure_rate(current['change_failure_rate'])})",
                f"- MTTR: {_format_metric(current['mttr_hours'], 'hours')} ({grade_mttr(current['mttr_hours'])})",
                "",
                "## Week-over-Week Delta",
                f"- Deployment Frequency: {_delta(current['deployment_frequency'], previous['deployment_frequency'])}",
                f"- Lead Time for Changes: {_delta(current['lead_time_hours'], previous['lead_time_hours'], 'hours')}",
                f"- Change Failure Rate: {_delta(current['change_failure_rate'], previous['change_failure_rate'])}",
                f"- MTTR: {_delta(current['mttr_hours'], previous['mttr_hours'], 'hours')}",
                "",
                "## DORA Grade Thresholds",
                "| Metric | Elite | High | Medium | Low |",
                "| --- | --- | --- | --- | --- |",
                "| Deployment Frequency (per week) | >= 7.0 | >= 1.0 | >= 0.25 | < 0.25 |",
                "| Lead Time for Changes (hours) | <= 24 | <= 168 | <= 720 | > 720 |",
                "| Change Failure Rate | <= 0.15 | <= 0.30 | <= 0.45 | > 0.45 |",
                "| MTTR (hours) | <= 24 | <= 168 | <= 720 | > 720 |",
            ]
        ),
        encoding="utf-8",
    )
    return path


def render_dashboard_image(rows: list[dict[str, Any]], output_file: Path) -> None:
    weeks = [row["week"] for row in rows]
    deployment = [row["deployment_frequency"] for row in rows]
    lead_time = [row["lead_time_hours"] for row in rows]
    failure_rate = [row["change_failure_rate"] for row in rows]
    mttr = [row["mttr_hours"] for row in rows]

    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    axes[0, 0].bar(weeks, deployment, color="#1f77b4")
    axes[0, 0].set_title("Deployment Frequency")

    axes[0, 1].plot(weeks, lead_time, marker="o", color="#ff7f0e")
    axes[0, 1].set_title("Lead Time for Changes (hours)")

    axes[1, 0].plot(weeks, failure_rate, marker="o", color="#d62728")
    axes[1, 0].set_title("Change Failure Rate")

    axes[1, 1].plot(weeks, mttr, marker="o", color="#2ca02c")
    axes[1, 1].set_title("MTTR (hours)")

    for axis in axes.flatten():
        axis.tick_params(axis="x", rotation=45)
        axis.grid(True, alpha=0.3)

    fig.tight_layout()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_file, dpi=150)
    plt.close(fig)


def generate_outputs() -> None:
    repository = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repository or not token:
        raise RuntimeError("GITHUB_REPOSITORY and GITHUB_TOKEN must be set")

    now = datetime.now(UTC)
    week_starts = recent_week_starts(now, count=12)
    week_labels = [iso_week_label(week_start) for week_start in week_starts]
    week_start_min = week_starts[0]

    api = GitHubApi(repository=repository, token=token)
    workflow_runs = api.fetch_deploy_workflow_runs()
    merged_prs = api.fetch_merged_pull_requests()
    incident_issues = api.fetch_incident_issues()

    deployment_frequency, successful_deploy_runs = compute_deployment_frequency(workflow_runs, week_labels, week_start_min)

    first_commit_dates: dict[int, datetime] = {}
    for pr in merged_prs:
        number = pr.get("number")
        if isinstance(number, int):
            first_commit = api.fetch_pr_first_commit_author_date(number)
            if first_commit:
                first_commit_dates[number] = first_commit

    lead_time_hours = compute_lead_time_for_changes(merged_prs, first_commit_dates, successful_deploy_runs, week_labels)
    change_failure_rate = compute_change_failure_rate(incident_issues, deployment_frequency, week_labels)
    mttr_hours = compute_mttr_hours(incident_issues, week_labels)

    rows = build_metric_rows(week_labels, deployment_frequency, lead_time_hours, change_failure_rate, mttr_hours)

    metrics_dir = Path("metrics")
    reports_dir = Path("reports")
    docs_images_dir = Path("docs/images")
    metrics_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    docs_images_dir.mkdir(parents=True, exist_ok=True)

    (metrics_dir / "dora.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    write_weekly_report(rows, reports_dir)
    render_dashboard_image(rows, docs_images_dir / "dora-dashboard.png")


if __name__ == "__main__":
    generate_outputs()
