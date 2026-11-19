import hmac

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
