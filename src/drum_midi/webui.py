"""Remote web UI for the Drum-to-MIDI pipeline (stdlib-only, token auth).

Serve a single-page control panel over HTTP so the pipeline can be driven from
another device while FL Studio runs on the desktop. Bind to 0.0.0.0 for LAN
access; every /api/* route requires the token (passed as ?token=...). The
token is generated at startup unless DRUM_WEB_TOKEN is set.

Endpoints:
    GET  /                 control panel HTML
    GET  /api/files        list audio files in the input dir
    GET  /api/meta         available kits and transcribe methods
    POST /api/run          {file, method, preset} -> {notes, count}
    POST /api/export       {file, method, preset} -> writes .mid, returns link
    GET  /api/export?path= download a written MIDI file

Run:  python -m drum_midi.webui [--host 0.0.0.0] [--port 8123] [--dir PATH]
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from drum_midi.audio import parse_audio
from drum_midi.editor import delete_note, move_note, reassign_note
from drum_midi.maps import DRUM_TYPES, PRESETS
from drum_midi.midi_out import write_midi
from drum_midi.transcribe import transcribe

AUDIO_EXTS = {".wav", ".wave", ".mp3", ".flac", ".ogg", ".m4a"}

STATIC_DIR = Path(__file__).resolve().parent / "webui_static"
STATIC_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "DrumMIDIWeb/1.0"

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, rel_path: str):
        if rel_path not in STATIC_TYPES:
            return self._deny("not found", 404)
        base = Path(getattr(self.server, "static_dir", None) or STATIC_DIR).resolve()
        candidate = (base / rel_path).resolve()
        if not candidate.is_relative_to(base):
            return self._deny("not found", 404)
        try:
            data = candidate.read_bytes()
        except OSError:
            return self._deny("not found", 404)
        return self._send(200, data, STATIC_TYPES[rel_path])

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode())

    def _deny(self, msg="forbidden", code=403):
        return self._json({"error": msg}, code)

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        return json.loads(self.rfile.read(n))

    def _authed(self) -> bool:
        token = self.headers.get("X-Auth-Token") or ""
        want = self.server.token
        # empty token server (loopback only) accepts anything; else constant-time cmp
        return (not want) or hmac.compare_digest(token, want)

    def _check_auth(self) -> bool:
        if self._authed():
            return True
        self._deny("unauthorized")
        return False

    def log_message(self, fmt, *args):
        if self.server.verbose:
            super().log_message(fmt, *args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/":
            return self._send_file("index.html")
        if path.startswith("/static/"):
            return self._send_file(urllib.parse.unquote(path[len("/static/"):]))
        if self._check_auth():
            if path == "/api/files":
                files = sorted(p.name for p in Path(self.server.input_dir).iterdir()
                               if p.suffix.lower() in AUDIO_EXTS)
                self._json({"files": files})
            elif path == "/api/meta":
                self._json({"kits": list(PRESETS.keys()),
                            "methods": ["trigger", "bands", "adtof", "strum", "dettato"],
                            "types": list(DRUM_TYPES)})
            else:
                self._deny("not found", 404)

    def do_POST(self):
        if self._check_auth():
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/upload":
                return self._upload()
            body = self._read_body()
            if path == "/api/run":
                self._run(body)
            elif path == "/api/edit":
                self._edit(body)
            elif path == "/api/export":
                self._export(body)
            else:
                self._deny("not found", 404)

    def _upload(self):
        q = urllib.parse.urlparse(self.path)
        name = urllib.parse.parse_qs(q.query).get("name", [""])[0]
        name = Path(name).name  # strip any path/traversal
        if not name or Path(name).suffix.lower() not in AUDIO_EXTS:
            return self._deny("name must be an audio file (.wav/.mp3/...)", 400)
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            return self._deny("empty upload", 400)
        data = self.rfile.read(n)
        if len(data) != n:
            return self._deny("short read", 400)
        base = Path(self.server.input_dir).resolve()
        out = (base / name).resolve()
        if not str(out).startswith(str(base)):
            return self._deny("bad path", 400)
        out.write_bytes(data)
        return self._json({"ok": True, "file": out.name})

    def _resolve(self, filename: str) -> Path | None:
        base = Path(self.server.input_dir).resolve()
        cand = (base / filename).resolve()
        if cand.is_file() and str(cand).startswith(str(base)):
            return cand
        return None

    def _run(self, body):
        fn = body.get("file", "")
        p = self._resolve(fn)
        if p is None:
            return self._deny("file not found")
        try:
            sr, x = parse_audio(p)
            notes = transcribe(x, sr, method=body.get("method", "trigger"),
                               threshold_preset=body.get("preset", "tuned-mixwave"),
                               groove=body.get("groove", True),
                               flatten_cymbal=body.get("flatten_cymbal", False),
                               velocity_smooth=body.get("velocity_smooth", False),
                               protect_grooves=body.get("protect_grooves", False))
            self.server.notes = notes
            self.server.last_file = p
            return self._json({"count": len(notes), "notes": notes})
        except Exception as e:  # surface real errors to the UI
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def _edit(self, body):
        notes = getattr(self.server, "notes", None)
        if notes is None:
            return self._deny("run transcription first", 409)
        try:
            idx = int(body["index"])
            action = body.get("action")
            if action == "delete":
                notes = delete_note(notes, idx)
            elif action == "move":
                notes = move_note(notes, idx, float(body.get("delta_s", 0)))
            elif action == "reassign":
                notes = reassign_note(notes, idx, body["type"])
            else:
                return self._deny(f"unknown action: {action}", 400)
            self.server.notes = notes
            return self._json({"count": len(notes), "notes": notes})
        except (KeyError, ValueError, TypeError, IndexError) as e:
            return self._json({"error": f"{type(e).__name__}: {e}"}, 400)

    def _export(self, body):
        notes = getattr(self.server, "notes", None)
        fp = getattr(self.server, "last_file", None)
        if notes is None or fp is None:
            return self._deny("run transcription first", 409)
        try:
            out = fp.with_suffix(".mid")
            write_midi(notes, out, preset=body.get("kit", "gm"))
            self._json({"ok": True, "path": out.name, "count": len(notes)})
        except Exception as e:
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def _parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Drum-to-MIDI remote web UI")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8123)
    ap.add_argument("--dir", default=None, help="input dir for audio files")
    ap.add_argument("--token", default=None, help="auth token (default: random)")
    ap.add_argument("--verbose", action="store_true")
    return ap.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    input_dir = args.dir or os.path.join(os.path.dirname(__file__), "..", "..", "challange")
    input_dir = os.path.abspath(input_dir)
    token = args.token or os.environ.get("DRUM_WEB_TOKEN") or secrets.token_urlsafe(16)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.token = token
    server.input_dir = input_dir
    server.verbose = args.verbose
    server.notes = None
    server.last_file = None

    print(f"Drum-MIDI web UI: http://{args.host}:{args.port}/")
    print(f"  input dir: {input_dir}")
    if args.host not in ("127.0.0.1", "localhost"):
        print(f"  token (LAN access): {token}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
