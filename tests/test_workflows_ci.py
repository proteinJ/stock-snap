from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_workflow(path: Path) -> dict:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    trigger = workflow.get("on", workflow.get(True))
    if trigger is not None:
        workflow["on"] = trigger
    return workflow


def test_ci_workflow_triggers_and_job_config() -> None:
    workflow = _load_workflow(REPO_ROOT / ".github" / "workflows" / "ci.yml")

    assert workflow["on"] == {
        "pull_request": {"branches": ["main"]},
        "push": {"branches": ["main"]},
    }
    assert workflow["permissions"] == {"contents": "read"}

    jobs = workflow["jobs"]
    assert set(jobs) == {"test"}

    steps = jobs["test"]["steps"]
    assert steps[0]["uses"] == "actions/checkout@v4"
    assert steps[1]["uses"] == "actions/setup-python@v5"
    assert steps[1]["with"] == {"python-version": "3.12", "cache": "pip"}
    assert steps[2]["run"] == "pip install -r requirements.txt"
    assert steps[3]["run"] == "pytest"


def test_pr_title_workflow_triggers_and_semantic_types() -> None:
    workflow = _load_workflow(REPO_ROOT / ".github" / "workflows" / "pr-title.yml")

    assert workflow["on"] == {
        "pull_request": {"types": ["opened", "edited", "synchronize", "reopened"]}
    }
    assert workflow["permissions"] == {"pull-requests": "read"}

    jobs = workflow["jobs"]
    assert set(jobs) == {"pr-title"}

    step = jobs["pr-title"]["steps"][0]
    assert step["uses"] == "amannn/action-semantic-pull-request@v5"
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
