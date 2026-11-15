from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_workflow(path: Path) -> dict:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    trigger = workflow.get("on", workflow.get(True))
    if trigger is not None:
        workflow["on"] = trigger
    return workflow


def _step_uses(job: dict) -> list[str]:
    return [step.get("uses", "") for step in job["steps"]]


def test_ci_workflow_runs_lint_then_matrix_tests() -> None:
    workflow = _load_workflow(REPO_ROOT / ".github" / "workflows" / "ci.yml")

    assert workflow["on"] == {
        "pull_request": {"branches": ["main"]},
        "push": {"branches": ["main"]},
    }
    assert workflow["permissions"] == {"contents": "read"}

    jobs = workflow["jobs"]
    assert set(jobs) == {"lint", "test"}
    assert "ruff check ." in [step.get("run") for step in jobs["lint"]["steps"]]

    test_job = jobs["test"]
    assert test_job["needs"] == "lint"
    assert test_job["runs-on"] == "${{ matrix.os }}"
    matrix = test_job["strategy"]["matrix"]
    assert matrix["os"] == ["ubuntu-latest", "macos-latest"]
    assert matrix["python-version"] == ["3.11", "3.12", "3.13"]

    steps = test_job["steps"]
    assert steps[0]["uses"].startswith("actions/checkout@")
    assert steps[1]["uses"].startswith("actions/setup-python@")
    assert steps[1]["with"]["python-version"] == "${{ matrix.python-version }}"
    assert steps[-1]["run"] == "pytest"


def test_ci_workflow_injects_secret_without_hardcoding() -> None:
    workflow = _load_workflow(REPO_ROOT / ".github" / "workflows" / "ci.yml")

    secret_envs = [
        step["env"]["STOCK_API_KEY"]
        for step in workflow["jobs"]["test"]["steps"]
        if "STOCK_API_KEY" in step.get("env", {})
    ]
    assert secret_envs == ["${{ secrets.STOCK_API_KEY }}"]


def test_deploy_workflow_runs_build_test_deploy_with_artifact() -> None:
    workflow = _load_workflow(REPO_ROOT / ".github" / "workflows" / "deploy.yml")

    jobs = workflow["jobs"]
    assert list(jobs) == ["build", "test", "deploy"]
    assert jobs["test"]["needs"] == "build"
    assert jobs["deploy"]["needs"] == "test"

    assert any(u.startswith("actions/upload-artifact@") for u in _step_uses(jobs["build"]))
    assert any(u.startswith("actions/download-artifact@") for u in _step_uses(jobs["test"]))
    assert any(u.startswith("actions/download-artifact@") for u in _step_uses(jobs["deploy"]))
    assert any(u.startswith("actions/deploy-pages@") for u in _step_uses(jobs["deploy"]))


def test_pr_title_workflow_triggers_and_semantic_types() -> None:
    workflow = _load_workflow(REPO_ROOT / ".github" / "workflows" / "pr-title.yml")

    assert workflow["on"] == {
        "pull_request": {"types": ["opened", "edited", "synchronize", "reopened"]}
    }
    assert workflow["permissions"] == {"pull-requests": "read"}

    jobs = workflow["jobs"]
    assert set(jobs) == {"pr-title"}

    step = jobs["pr-title"]["steps"][0]
    assert step["uses"].startswith("amannn/action-semantic-pull-request@")
    assert step["env"] == {"GITHUB_TOKEN": "${{ secrets.GITHUB_TOKEN }}"}
    assert step["with"]["types"].splitlines() == [
        "feat",
        "fix",
        "docs",
        "ci",
        "test",
        "refactor",
        "chore",
    ]