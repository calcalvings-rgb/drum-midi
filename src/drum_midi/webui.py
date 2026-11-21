"""GrooveForge web editor and transcription engine (stdlib HTTP server).

The browser sends its private URL/session token in X-Auth-Token for every
/api route. Public routes are the application assets and /source.zip.
Legacy /api/run, /api/edit and /api/export remain for existing clients.
The new editor uses /api/editor/import and /api/editor/export for per-tab
note snapshots, and /api/audio for authenticated reference loading.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import shutil
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from drum_midi.audio import parse_audio
from drum_midi.editor import delete_note, move_note, reassign_note
from drum_midi.maps import DRUM_TYPES, PRESETS
from drum_midi.midi_out import write_midi
from drum_midi.transcribe import THRESHOLD_PRESETS, transcribe
from drum_midi.web_editor import read_editor_midi, write_editor_midi
from drum_midi.source_offer import build_source_archive

AUDIO_EXTS = {".wav", ".wave", ".mp3", ".flac", ".ogg", ".m4a"}

_RUN_LOCK = threading.Lock()

MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_AUDIO_BYTES = 256 * 1024 * 1024


class RequestError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


STATIC_DIR = Path(__file__).resolve().parent / "webui_static"
STATIC_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
}


_MANIFEST = STATIC_DIR / "asset_manifest.json"
if _MANIFEST.exists():
    STATIC_TYPES.update(json.loads(_MANIFEST.read_text(encoding="utf-8")))


class Handler(BaseHTTPRequestHandler):
    server_version = "DrumMIDIWeb/1.0"

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
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

    def _raw_body(self, limit, allow_empty=False):
        if self.headers.get("Transfer-Encoding"):
            raise RequestError("Chunked requests are not supported")
        try:
            size = int(self.headers.get("Content-Length") or 0)
        except (ValueError, TypeError):
            raise RequestError("Invalid Content-Length")
        if size < 0 or (size == 0 and not allow_empty):
            raise RequestError("Empty request")
        if size > limit:
            raise RequestError("Request exceeds the size limit", 413)
        connection = getattr(self, "connection", None)
        if connection is not None:
            connection.settimeout(30)
        data = self.rfile.read(size)
        if len(data) != size:
            raise RequestError("Incomplete request body")
        return data

    def _read_body(self):
        raw = self._raw_body(MAX_JSON_BYTES, allow_empty=True)
        def invalid_constant(value):
            raise ValueError("Non-finite JSON numbers are not allowed")
        body = json.loads(raw, parse_constant=invalid_constant) if raw else {}
        if not isinstance(body, dict):
            raise RequestError("Expected a JSON object")
        return body


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
        if path == "/source.zip":
            try:
                return self._send(200, build_source_archive(), "application/zip")
            except (OSError, ValueError, TypeError) as error:
                return self._json({"error": "Source bundle unavailable; check the release source manifest"}, 503)
        if path == "/":
            return self._send_file("index.html")
        if path.startswith("/static/"):
            return self._send_file(urllib.parse.unquote(path[len("/static/"):]))
        if self._check_auth():
            if path == "/api/audio":
                filename = urllib.parse.parse_qs(parsed.query).get("file", [""])[0]
                audio = self._resolve(filename)
                if audio is None or audio.suffix.lower() not in AUDIO_EXTS:
                    return self._deny("file not found", 404)
                size = audio.stat().st_size
                if size > MAX_AUDIO_BYTES:
                    return self._deny("Audio exceeds 256 MiB", 413)
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav" if audio.suffix.lower() in {".wav", ".wave"} else "application/octet-stream")
                self.send_header("Content-Length", str(size))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                with audio.open("rb") as stream:
                    shutil.copyfileobj(stream, self.wfile)
                return
            if path == "/api/files":
                base = Path(self.server.input_dir).resolve()
                files = sorted(p.name for p in base.iterdir()
                               if p.is_file() and p.resolve().is_relative_to(base) and p.suffix.lower() in AUDIO_EXTS)
                self._json({"files": files})
            elif path == "/api/meta":
                self._json({"kits": list(PRESETS.keys()),
                            "methods": ["trigger", "bands", "adtof", "strum", "dettato"],
                            "types": list(DRUM_TYPES), "gm_map": PRESETS["gm"],
                            "presets": list(THRESHOLD_PRESETS)})
            else:
                self._deny("not found", 404)

    def do_POST(self):
        if not self._check_auth():
            return
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/upload":
                return self._upload()
            if path == "/api/editor/import":
                return self._json(read_editor_midi(self._raw_body(MAX_JSON_BYTES)))
            body = self._read_body()
            if path == "/api/editor/export":
                return self._send(200, write_editor_midi(body), "audio/midi")
            if path == "/api/run":
                return self._run(body)
            if path == "/api/edit":
                return self._edit(body)
            if path == "/api/export":
                return self._export(body)
            return self._deny("not found", 404)
        except RequestError as error:
            return self._json({"error": str(error)}, error.status)
        except (ValueError, TypeError, KeyError, UnicodeError, OSError, EOFError) as error:
            return self._json({"error": str(error)}, 400)
        except RuntimeError as error:
            return self._json({"error": str(error)}, 503)


    def _upload(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = query.get("name", [""])[0].replace("\\", "/").split("/")[-1]
        if not name or Path(name).suffix.lower() not in AUDIO_EXTS or any(ord(c) < 32 for c in name):
            return self._deny("name must be an audio file (.wav/.mp3/...)", 400)
        try:
            data = self._raw_body(MAX_AUDIO_BYTES)
            base = Path(self.server.input_dir).resolve()
            for suffix in range(10000):
                candidate = Path(name) if suffix == 0 else Path(f"{Path(name).stem}_{suffix}{Path(name).suffix}")
                out = (base / candidate).resolve()
                if not out.is_relative_to(base):
                    return self._deny("bad path", 400)
                try:
                    with out.open("xb") as stream:
                        stream.write(data)
                    return self._json({"ok": True, "file": out.name})
                except FileExistsError:
                    continue
            return self._deny("Too many files with that name", 409)
        except RequestError as error:
            return self._json({"error": str(error)}, error.status)
        except (OSError, ValueError) as error:
            return self._json({"error": str(error)}, 400)


    def _resolve(self, filename: str) -> Path | None:
        base = Path(self.server.input_dir).resolve()
        cand = (base / filename).resolve()
        if cand.is_file() and cand.is_relative_to(base):
            return cand
        return None

    def _run(self, body):
        fn = body.get("file", "")
        p = self._resolve(fn)
        if p is None:
            return self._deny("file not found")
        if p.stat().st_size > MAX_AUDIO_BYTES:
            return self._deny("Audio exceeds 256 MiB", 413)
        if not _RUN_LOCK.acquire(blocking=False):
            return self._deny("This engine is already transcribing; wait and retry", 409)
        try:
            sr, x = parse_audio(p) if p.suffix.lower() in {".wav", ".wave"} else parse_audio(p, decode_mp3=True)
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
        finally:
            _RUN_LOCK.release()

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
    Path(input_dir).mkdir(parents=True, exist_ok=True)
    token = args.token or os.environ.get("DRUM_WEB_TOKEN") or secrets.token_urlsafe(16)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.token = token
    server.input_dir = input_dir
    server.verbose = args.verbose
    server.notes = None
    server.last_file = None

    print(f"GrooveForge web UI: http://{args.host}:{server.server_port}/?token={urllib.parse.quote(token)}")
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
