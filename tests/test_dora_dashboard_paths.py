from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_dora_dashboard_fetch_path_matches_deploy_copy_filename() -> None:
    dora_html = (REPO_ROOT / "site" / "dora.html").read_text(encoding="utf-8")
    deploy_workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")

    fetch_match = re.search(r"fetch\('./([^']+\.json)'", dora_html)
    assert fetch_match, "dora.html must fetch a json file for dashboard data"

    copy_match = re.search(r"cp\s+metrics/dora\.json\s+site/([^\s]+\.json)", deploy_workflow)
    assert copy_match, "deploy.yml must copy DORA metrics json into site/"

    assert fetch_match.group(1) == copy_match.group(1)
