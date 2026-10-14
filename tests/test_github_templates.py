from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_issue_template_config_disables_blank_issues() -> None:
    config = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8")
    assert "blank_issues_enabled: false" in config


def test_bug_issue_template_fields_and_defaults() -> None:
    bug_template = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "bug.yml").read_text(encoding="utf-8")

    assert "name: Bug" in bug_template
    assert "labels: [bug]" in bug_template
    for required_field in ("현상", "재현 단계", "기대 동작"):
        assert required_field in bug_template
    for area in ("collector", "analysis", "site", "dora", "workflow"):
        assert f"- {area}" in bug_template
    for priority in ("- p1", "- p2", "- p3"):
        assert priority in bug_template
    assert "운영 장애인가요?" in bug_template
    assert "incident" in bug_template
    assert "이전에는 동작했나요?" in bug_template
    assert "kind:regression" in bug_template


def test_feature_issue_template_fields_and_defaults() -> None:
    feature_template = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature.yml").read_text(encoding="utf-8")

    assert "name: Feature" in feature_template
    assert "labels: [enhancement]" in feature_template
    for required_field in ("배경", "작업 내용", "완료 조건"):
        assert required_field in feature_template
    for area in ("collector", "analysis", "site", "dora", "workflow"):
        assert f"- {area}" in feature_template
    for priority in ("- p1", "- p2", "- p3"):
        assert priority in feature_template
    for effort in ('- "1"', '- "2"', '- "3"', '- "5"', '- "8"'):
        assert effort in feature_template
    assert "- [ ] ..." in feature_template


def test_pull_request_template_sections() -> None:
    pull_request_template = (REPO_ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")

    for section in ("## 변경 요약", "## 관련 이슈", "Closes #", "## 테스트 방법", "## 체크리스트"):
        assert section in pull_request_template


def test_readme_has_label_rules_table() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "## 7. 라벨 규칙" in readme
    assert "유형 (`bug` / `enhancement` / `documentation` / `incident`)" in readme
    assert "우선순위 (`priority:p1` ~ `priority:p3`)" in readme
    assert "영역 (`area:*`)" in readme
