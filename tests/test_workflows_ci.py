import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_workflow(path: Path) -> dict:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    trigger = workflow.get("on", workflow.get(True))
    if trigger is not None:
        workflow["on"] = trigger
    return workflow


WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SETUP_ACTION = "./.github/actions/setup-python-env"
REUSABLE_TEST = "./.github/workflows/reusable-test.yml"


def _step_uses(job: dict) -> list[str]:
    return [step.get("uses", "") for step in job["steps"]]


def test_composite_action_sets_up_python_with_venv_cache() -> None:
    action = yaml.safe_load(
        (REPO_ROOT / ".github" / "actions" / "setup-python-env" / "action.yml").read_text(encoding="utf-8")
    )

    assert action["runs"]["using"] == "composite"
    assert set(action["inputs"]) == {"python-version", "cache"}
    steps = action["runs"]["steps"]
    assert steps[0]["uses"].startswith("actions/setup-python@")
    cache_step = next(step for step in steps if step.get("uses", "").startswith("actions/cache@"))
    assert cache_step["with"]["path"] == ".venv"
    assert "hashFiles('requirements.txt')" in cache_step["with"]["key"]


def test_ci_workflow_runs_lint_then_reusable_matrix_tests() -> None:
    workflow = _load_workflow(WORKFLOWS / "ci.yml")

    assert workflow["on"] == {
        "pull_request": {"branches": ["main"]},
        "push": {"branches": ["main"]},
    }
    assert workflow["permissions"] == {"contents": "read"}

    jobs = workflow["jobs"]
    assert set(jobs) == {"lint", "test"}
    assert SETUP_ACTION in _step_uses(jobs["lint"])
    assert "ruff check ." in [step.get("run") for step in jobs["lint"]["steps"]]

    test_job = jobs["test"]
    assert test_job["needs"] == "lint"
    assert test_job["uses"] == REUSABLE_TEST
    assert test_job["secrets"] == {"STOCK_API_KEY": "${{ secrets.STOCK_API_KEY }}"}

    matrix = json.loads(test_job["with"]["matrix"])
    assert matrix["os"] == ["ubuntu-latest", "macos-latest"]
    assert matrix["python-version"] == ["3.11", "3.12", "3.13"]
    assert matrix["exclude"] == [{"os": "macos-latest", "python-version": "3.11"}]
    assert matrix["include"] == [{"os": "windows-latest", "python-version": "3.12"}]


def test_reusable_test_workflow_uses_matrix_input_and_secret() -> None:
    workflow = _load_workflow(WORKFLOWS / "reusable-test.yml")

    call = workflow["on"]["workflow_call"]
    assert "matrix" in call["inputs"]
    assert call["secrets"]["STOCK_API_KEY"]["required"] is False

    job = workflow["jobs"]["pytest"]
    assert job["runs-on"] == "${{ matrix.os }}"
    assert job["strategy"]["matrix"] == "${{ fromJSON(inputs.matrix) }}"
    assert SETUP_ACTION in _step_uses(job)

    secret_envs = [
        step["env"]["STOCK_API_KEY"] for step in job["steps"] if "STOCK_API_KEY" in step.get("env", {})
    ]
    assert secret_envs == ["${{ secrets.STOCK_API_KEY }}"]
    assert job["steps"][-1]["run"] == "pytest"


def test_deploy_workflow_is_selective_and_runs_build_test_deploy() -> None:
    workflow = _load_workflow(WORKFLOWS / "deploy.yml")

    assert "site/**" in workflow["on"]["push"]["paths"]
    assert "site/**" in workflow["on"]["pull_request"]["paths"]
    assert "workflow_dispatch" in workflow["on"]

    jobs = workflow["jobs"]
    assert list(jobs) == ["build", "test", "deploy"]
    assert jobs["test"]["needs"] == "build"
    assert jobs["test"]["uses"] == REUSABLE_TEST
    assert jobs["deploy"]["needs"] == "test"
    assert "refs/heads/main" in jobs["deploy"]["if"]
    assert "pull_request" in jobs["deploy"]["if"]

    assert any(u.startswith("actions/upload-artifact@") for u in _step_uses(jobs["build"]))
    assert any(u.startswith("actions/download-artifact@") for u in _step_uses(jobs["deploy"]))
    assert any(u.startswith("actions/deploy-pages@") for u in _step_uses(jobs["deploy"]))


def test_dora_workflow_reuses_setup_action() -> None:
    workflow = _load_workflow(WORKFLOWS / "dora.yml")

    assert SETUP_ACTION in _step_uses(workflow["jobs"]["collect"])


def test_cache_benchmark_compares_cache_off_and_on() -> None:
    workflow = _load_workflow(WORKFLOWS / "cache-benchmark.yml")

    jobs = workflow["jobs"]
    assert set(jobs) == {"no-cache", "with-cache", "report"}
    assert jobs["report"]["needs"] == ["no-cache", "with-cache"]

    def setup_cache_input(job: dict) -> str:
        step = next(s for s in job["steps"] if s.get("uses") == SETUP_ACTION)
        return step["with"]["cache"]

    assert setup_cache_input(jobs["no-cache"]) == "false"
    assert setup_cache_input(jobs["with-cache"]) == "true"


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