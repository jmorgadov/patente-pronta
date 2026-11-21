from pathlib import Path

import pytest

from patente_pronta.guides import GUIDES_DIR, guide_links, load_guide

GUIDE = """# Limiti di velocità

## Fonti

| Veicolo | Autostrada |
| :--- | ---: |
| Autovettura<br>Motociclo | 130 |

Vedi [distanza](distanza-di-sicurezza.md#fonti) e [fonti](#fonti).
"""


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    (tmp_path / "limiti.md").write_text(GUIDE)
    (tmp_path / "distanza.md").write_text("# Distanza\n\nTesto.\n")
    return tmp_path


def test_guide_links_are_sorted_by_slug_and_titled_by_heading(directory: Path) -> None:
    links = guide_links(directory)

    assert [(link.slug, link.title) for link in links] == [
        ("distanza", "Distanza"),
        ("limiti", "Limiti di velocità"),
    ]


def test_load_guide_renders_markdown_without_the_title(directory: Path) -> None:
    guide = load_guide(directory, "limiti")

    assert guide.title == "Limiti di velocità"
    assert "<h1" not in guide.html
    assert '<h2 id="fonti">Fonti</h2>' in guide.html
    assert '<td style="text-align: right;">130</td>' in guide.html
    assert "Autovettura<br>Motociclo" in guide.html


def test_load_guide_points_guide_links_to_the_app(directory: Path) -> None:
    html = load_guide(directory, "limiti").html

    assert 'href="/guide/distanza-di-sicurezza#fonti"' in html
    assert 'href="#fonti"' in html


@pytest.mark.parametrize("slug", ["missing", "../limiti", "Limiti"])
def test_load_guide_rejects_unknown_slugs(directory: Path, slug: str) -> None:
    with pytest.raises(LookupError):
        load_guide(directory, slug)


def test_load_guide_requires_a_title(directory: Path) -> None:
    (directory / "untitled.md").write_text("Solo testo.\n")

    with pytest.raises(ValueError, match="title"):
        load_guide(directory, "untitled")


def test_every_shipped_guide_renders() -> None:
    links = guide_links(GUIDES_DIR)

    assert links
    for link in links:
        assert "<table>" in load_guide(GUIDES_DIR, link.slug).html
