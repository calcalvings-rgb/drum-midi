from html.parser import HTMLParser
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "src/drum_midi/webui_static"


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_frontend_has_accessible_workspace_and_external_module():
    parser = Elements()
    parser.feed((STATIC / "index.html").read_text(encoding="utf-8"))
    elements = parser.elements
    assert any(tag == "main" for tag, _ in elements)
    assert any(tag == "script" and a.get("type") == "module" and a.get("src") == "/static/app.js" for tag, a in elements)
    assert any(a.get("id") == "status" and a.get("role") == "status" for _, a in elements)
    assert any(a.get("id") == "mount" for _, a in elements)
    assert any(a.get("id") == "stage" and a.get("aria-label") == "Piano roll" for _, a in elements)
    ids = [a["id"] for _, a in elements if "id" in a]
    assert len(ids) == len(set(ids))
    for required in ["file", "wav", "midi", "kit", "method", "groove", "flatten", "velsmooth", "protgrooves", "run", "export", "summary", "filter", "zoom-out", "fit", "zoom-in", "mount", "stage", "undo", "redo", "velocity", "drop-zone", "drop-files"]:
        assert required in ids
    for tag, a in elements:
        if tag in {"select", "input"}:
            assert a.get("aria-label") or any(t == "label" and b.get("for") == a.get("id") for t, b in elements)


def test_frontend_uses_local_assets_only():
    parser = Elements()
    parser.feed((STATIC / "index.html").read_text(encoding="utf-8"))
    for tag, attrs in parser.elements:
        if tag in {"script", "link", "img"}:
            resource = attrs.get("src", attrs.get("href", ""))
            assert not resource.startswith(("http", "//"))


def test_music_workspace_has_direct_copy_and_no_invented_brand_asset():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "—" not in html
    assert "From real drums." not in html
    assert "brand-mark" not in html
    assert "empty-roll" not in html
    assert 'id="take-name"' in html
