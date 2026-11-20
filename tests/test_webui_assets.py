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
    assert any(a.get("id") == "roll" and a.get("tabindex") == "0" for _, a in elements)
    ids = [a["id"] for _, a in elements if "id" in a]
    assert len(ids) == len(set(ids))
    for required in ["file", "upfile", "upbtn", "kit", "method", "groove", "flatten", "velsmooth", "protgrooves", "run", "export", "results", "summary", "filter", "zout", "zfit", "zin", "legend", "rollwrap", "roll", "sel", "selinfo", "seltype", "mvL", "mvR", "seldel"]:
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
