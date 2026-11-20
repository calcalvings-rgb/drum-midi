import hmac

import pytest

from drum_midi.webui import Handler


def _handler(token="secret"):
    h = Handler.__new__(Handler)
    h.server = type("S", (), {"token": token, "input_dir": None, "verbose": False})()
    return h


def test_authed_correct_token():
    h = _handler("secret")
    h.headers = type("H", (), {"get": lambda self, k, d=None: "secret"})()
    assert h._authed()


def test_authed_wrong_token():
    h = _handler("secret")
    h.headers = type("H", (), {"get": lambda self, k, d=None: "wrong"})()
    assert not h._authed()


def test_authed_empty_server_token_accepts_all():
    h = _handler("")
    h.headers = type("H", (), {"get": lambda self, k, d=None: ""})()
    assert h._authed()


def test_authed_constant_time_cmp_uses_digest():
    # ensure we are really doing digest comparison, not plain ==
    assert hmac.compare_digest("a" * 64, "b" * 64) is False


def test_resolve_blocks_path_traversal():
    h = _handler()
    h.server.input_dir = "C:/Users/ccalv/workspace/coding/drum-midi/challange"
    assert h._resolve("tes2.wav") is not None
    assert h._resolve("../trigger.py") is None
    assert h._resolve("..\\..\\src") is None
    assert h._resolve("../../../../windows/system32/win.ini") is None
    assert h._resolve("te%2e%2e") is None


def _edit(handler, body, notes=None):
    handler.server.notes = notes
    handler._json = lambda obj, code=200: (obj, code)
    return handler._edit(body)


def test_edit_delete_and_move():
    h = _handler()
    notes = [{"type": "kick", "onset_s": 0.5, "velocity": 0.5},
             {"type": "snare", "onset_s": 1.0, "velocity": 0.5}]
    obj, code = _edit(h, {"action": "delete", "index": 0}, notes)
    assert code == 200 and len(obj["notes"]) == 1 and obj["notes"][0]["type"] == "snare"
    obj, code = _edit(h, {"action": "move", "index": 0, "delta_s": 0.01}, notes)
    assert obj["notes"][0]["onset_s"] == pytest.approx(0.51)


def test_edit_reassign_rejects_unknown_type():
    h = _handler()
    notes = [{"type": "kick", "onset_s": 0.5, "velocity": 0.5}]
    obj, code = _edit(h, {"action": "reassign", "index": 0, "type": "nope"}, notes)
    assert code == 400


def test_edit_requires_run_first():
    h = _handler()
    h.server.notes = None
    h._json = lambda obj, code=200: (obj, code)
    obj, code = h._edit({"action": "delete", "index": 0})
    assert code == 409


def test_run_forwards_groove_and_flatten(tmp_path, monkeypatch):
    from drum_midi import webui
    h = _handler()
    h.server.input_dir = str(tmp_path)
    (tmp_path / "a.wav").write_bytes(b"dummy")
    captured = {}
    monkeypatch.setattr(webui, "parse_audio", lambda p: (44100, None))
    monkeypatch.setattr(webui, "transcribe",
                        lambda x, sr, **kw: (captured.update(kw), [])[1])
    h._json = lambda obj, code=200: (obj, code)
    obj, code = h._run({"file": "a.wav", "method": "trigger",
                         "groove": False, "flatten_cymbal": True,
                         "velocity_smooth": True, "protect_grooves": True})
    assert code == 200
    assert captured.get("groove") is False
    assert captured.get("flatten_cymbal") is True
    assert captured.get("velocity_smooth") is True
    assert captured.get("protect_grooves") is True


def test_run_defaults_groove_on():
    from drum_midi import webui
    h = _handler()
    h.server.input_dir = "C:/Users/ccalv/workspace/coding/drum-midi/challange"
    captured = {}
    h._json = lambda obj, code=200: (obj, code)
    monkeypatch = None
    original_parse = webui.parse_audio
    original_transcribe = webui.transcribe
    try:
        webui.parse_audio = lambda p: (44100, None)
        webui.transcribe = lambda x, sr, **kw: (captured.update(kw), [])[1]
        obj, code = h._run({"file": "tes2.wav", "method": "trigger"})
    finally:
        webui.parse_audio = original_parse
        webui.transcribe = original_transcribe
    assert code == 200
    assert captured.get("groove") is True
    assert captured.get("flatten_cymbal") is False


def test_upload_saves_audio_file(tmp_path):
    h = _handler()
    h.server.input_dir = str(tmp_path)
    h._json = lambda obj, code=200: (obj, code)
    h.path = "/api/upload?name=kick.wav"
    h.headers = type("H", (), {"get": lambda self, k, d=None: "4"})()
    h.rfile = type("R", (), {"read": lambda self, n: b"RIFF"})()
    obj, code = h._upload()
    assert code == 200 and obj["file"] == "kick.wav"
    assert (tmp_path / "kick.wav").read_bytes() == b"RIFF"


def test_upload_sanitizes_path_traversal(tmp_path):
    h = _handler()
    h.server.input_dir = str(tmp_path)
    h._json = lambda obj, code=200: (obj, code)
    h.path = "/api/upload?name=../../../../evil.wav"
    h.headers = type("H", (), {"get": lambda self, k, d=None: "1"})()
    h.rfile = type("R", (), {"read": lambda self, n: b"x"})()
    obj, code = h._upload()
    assert code == 200 and obj["file"] == "evil.wav"
    assert (tmp_path / "evil.wav").exists()


def test_upload_rejects_bad_extension(tmp_path):
    h = _handler()
    h.server.input_dir = str(tmp_path)
    h._json = lambda obj, code=200: (obj, code)
    h.path = "/api/upload?name=evil.exe"
    obj, code = h._upload()
    assert code == 400

@pytest.mark.parametrize("name,ctype", [("index.html", "text/html"), ("app.js", "text/javascript"), ("style.css", "text/css")])
def test_static_serves_asset(tmp_path, name, ctype):
    h = _handler()
    h.server.static_dir = tmp_path
    h.headers = {}
    (tmp_path / name).write_bytes(b"asset content")
    h.path = "/" if name == "index.html" else "/static/" + name
    h._send = lambda code, body, ctype="application/json": (code, body, ctype)
    code, body, content_type = h.do_GET()
    assert code == 200
    assert body == b"asset content"
    assert content_type.startswith(ctype)


@pytest.mark.parametrize("path", [
    "/static/../outside.js", "/static/%2e%2e/outside.js",
    "/static/..%5coutside.js", "/static/%2fetc/passwd",
    "/static/evil.exe", "/static/missing.js", "/static/app.js/extra",
    "/static/%00app.js", "/static/", "/static/../webui_static-other/app.js",
])
def test_static_rejects_unsafe_or_unknown_assets(tmp_path, path):
    h = _handler()
    h.server.static_dir = tmp_path
    h.headers = {}
    (tmp_path / "evil.exe").write_bytes(b"private")
    (tmp_path.parent / "outside.js").write_bytes(b"private")
    h.path = path
    h._send = lambda code, body, ctype="application/json": (code, body, ctype)
    responses = []
    h._send = lambda code, body, ctype="application/json": responses.append((code, body))
    h.do_GET()
    assert responses[0][0] == 404


def test_api_still_requires_auth_with_public_assets():
    h = _handler()
    h.path = "/api/meta"
    h.headers = {"X-Auth-Token": "wrong"}
    h._send = lambda code, body, ctype="application/json": (code, body, ctype)
    responses = []
    h._send = lambda code, body, ctype="application/json": responses.append((code, body))
    h.do_GET()
    assert responses[0][0] == 403
