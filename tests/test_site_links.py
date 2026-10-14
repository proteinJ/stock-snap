from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


SITE_DIR = Path(__file__).resolve().parents[1] / "site"
SKIPPED_SCHEMES = ("http", "https", "mailto", "tel", "javascript", "data")


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for attribute, value in attrs:
            if attribute in {"href", "src"} and value:
                self.links.append(value)


def iter_relative_links(html_file: Path) -> list[str]:
    parser = LinkParser()
    parser.feed(html_file.read_text(encoding="utf-8"))
    relative_links: list[str] = []

    for link in parser.links:
        parsed = urlparse(link)
        if (
            parsed.scheme in SKIPPED_SCHEMES
            or link.startswith("//")
            or link.startswith("#")
        ):
            continue
        if not parsed.path:
            continue
        relative_links.append(parsed.path)

    return relative_links


def test_site_relative_links_point_to_existing_files() -> None:
    missing_targets: list[str] = []

    for html_file in SITE_DIR.glob("*.html"):
        for relative_link in iter_relative_links(html_file):
            target_file = (html_file.parent / relative_link).resolve()
            if not target_file.is_file():
                missing_targets.append(f"{html_file.name} -> {relative_link}")

    assert not missing_targets, (
        "Broken relative links found in site/: " + ", ".join(sorted(missing_targets))
    )
