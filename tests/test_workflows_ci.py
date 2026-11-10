from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ci_workflow_triggers_and_job_config() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "branches: [main]" in workflow
    assert "permissions:" in workflow
    assert "contents: read" in workflow
    assert "jobs:" in workflow
    assert "test:" in workflow
    assert "python-version: '3.12'" in workflow
    assert "cache: pip" in workflow
    assert "pip install -r requirements.txt" in workflow
    assert "run: pytest" in workflow


def test_pr_title_workflow_triggers_and_semantic_types() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "pr-title.yml").read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "types: [opened, edited, synchronize, reopened]" in workflow
    assert "permissions:" in workflow
    assert "pull-requests: read" in workflow
    assert "jobs:" in workflow
    assert "pr-title:" in workflow
    assert "amannn/action-semantic-pull-request@v5" in workflow
    for cc_type in ("feat", "fix", "docs", "ci", "test", "refactor", "chore"):
        assert f"            {cc_type}" in workflow
