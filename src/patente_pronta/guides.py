import re
from pathlib import Path

import markdown

from patente_pronta.models import Guide, GuideLink

GUIDES_DIR = Path(__file__).parent / "guides"
GUIDES_URL = "/guide"
SLUG = re.compile(r"^[a-z0-9-]+$")
TITLE = re.compile(r"^# (.+)$", re.MULTILINE)
GUIDE_HREF = re.compile(r'href="([a-z0-9-]+)\.md(#[^"]*)?"')


def guide_links(directory: Path) -> list[GuideLink]:
    return [
        GuideLink(slug=path.stem, title=_title(path.read_text()))
        for path in sorted(directory.glob("*.md"))
    ]


def load_guide(directory: Path, slug: str) -> Guide:
    path = directory / f"{slug}.md"
    if not SLUG.match(slug) or not path.is_file():
        raise LookupError(f"Guida {slug!r} non trovata")
    text = path.read_text()
    return Guide(slug=slug, title=_title(text), html=_render(_without_title(text)))


def _title(text: str) -> str:
    match = TITLE.search(text)
    if match is None:
        raise ValueError("A guide must start with a '# ' title")
    return match.group(1).strip()


def _without_title(text: str) -> str:
    return TITLE.sub("", text, count=1)


def _render(text: str) -> str:
    html = markdown.markdown(text, extensions=["tables", "toc"])
    return GUIDE_HREF.sub(lambda m: f'href="{GUIDES_URL}/{m[1]}{m[2] or ""}"', html)
