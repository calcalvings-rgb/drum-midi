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

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Drum → MIDI</title>
<style>
  body{font:14px/1.5 system-ui,sans-serif;max-width:760px;margin:24px auto;padding:0 16px;background:#0f1115;color:#e6e8ec}
  h1{font-size:20px;margin:0 0 4px}
  .sub{color:#9aa2ae;margin:0 0 20px;font-size:13px}
  .card{background:#171a21;border:1px solid #262b36;border-radius:10px;padding:16px;margin-bottom:14px}
  label{display:block;font-size:12px;color:#9aa2ae;margin:10px 0 4px}
  select,input[type=text]{width:100%;box-sizing:border-box;padding:8px;background:#0f1115;color:#e6e8ec;border:1px solid #2c3340;border-radius:6px}
  button{padding:9px 18px;border:0;border-radius:6px;background:#4f7cff;color:#fff;font-size:14px;cursor:pointer;margin-top:14px}
  button.secondary{background:#2a3040;margin-left:8px}
  button:disabled{opacity:.5;cursor:default}
  #status{margin-top:12px;font-size:13px;min-height:20px}
  table{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}
  th,td{text-align:left;padding:5px 8px;border-bottom:1px solid #232834}
  th{color:#9aa2ae;font-weight:600}
  .badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;background:#232a3a;color:#aeb8c9}
  .badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;background:#232a3a;color:#aeb8c9}
  .t-kick{background:#5a1f24;color:#ffb3b3}
  .t-snare{background:#1f3a5a;color:#a9d4ff}
  .t-floor,.t-rack1,.t-rack2{background:#4a3a1a;color:#ffe3a3}
  .t-crash1,.t-crash2{background:#3a2b4a;color:#d9b9ff}
  .t-hat_closed,.t-hat_open,.t-ride,.t-ride_bell{background:#2a2f3a;color:#cdd4de}
  .rowbtn{margin:0 2px;padding:3px 7px;font-size:12px;background:#2a3040;border-radius:4px}
  .rowbtn.del{background:#4a2228}
  td select{width:auto;padding:2px 4px;font-size:12px;margin-right:4px}
  .velbar{display:inline-block;height:8px;border-radius:4px;background:#4f7cff;vertical-align:middle}
  .mono{font-family:ui-monospace,Consolas,monospace}
  .legend{margin-top:10px;font-size:12px;line-height:2}
  .legend .badge{margin-right:10px}
  #filter{width:180px;display:inline-block;margin-left:8px}
  #roll{display:block;width:100%;height:auto}
</style></head><body>
<h1>Drum → MIDI</h1>
<p class="sub">Trigger backend · remote control</p>

<div class="card">
  <label for="file">Audio file</label>
  <select id="file"></select>
  <div style="margin-top:10px;display:flex;gap:8px">
    <input type="file" id="upfile" accept="audio/*" style="flex:1">
    <button id="upbtn" class="secondary">Upload</button>
  </div>
  <label for="kit">Kit preset</label>
  <select id="kit"></select>
  <label for="method">Transcribe method</label>
  <select id="method">
    <option value="trigger">trigger (global-onset+classifier)</option>
    <option value="bands">bands (band-split flux)</option>
    <option value="adtof">adtof (neural, needs torch)</option>
    <option value="strum">strum (neural, needs torch)</option>
  </select>
  <button id="run">Run</button>
  <button id="export" class="secondary" disabled>Export MIDI</button>
  <div id="status"></div>
</div>

<div class="card" id="results" style="display:none">
  <div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px">
    <div id="summary" style="font-weight:600"></div>
    <select id="filter"><option value="">all types</option></select>
  </div>
  <div id="legend" class="legend"></div>
  <div id="rollwrap" style="position:relative;overflow-x:auto;border:1px solid #262b36;border-radius:8px">
    <canvas id="roll"></canvas>
  </div>
  <div id="sel" style="display:none;margin-top:10px;padding:10px;background:#0f1115;border:1px solid #262b36;border-radius:8px">
    <span style="color:#9aa2ae;font-size:12px">selected →</span>
    <span id="selinfo" style="font-weight:600;margin:0 8px"></span>
    <select id="seltype"></select>
    <button id="mvL" class="rowbtn">−10ms</button>
    <button id="mvR" class="rowbtn">+10ms</button>
    <button id="seldel" class="rowbtn del">del</button>
  </div>
</div>

<script>
const token = new URLSearchParams(location.search).get("token") || "";
const TYPES = [];
async function api(path, opts) {
  const o = opts || {};
  o.headers = { "Content-Type": "application/json", "X-Auth-Token": token };
  const r = await fetch(path, o);
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.status);
  return j;
}
async function init() {
  const meta = await api("/api/meta", { method: "GET" });
  TYPES.push(...meta.types);
  const sel = document.getElementById("kit");
  meta.kits.forEach(k => { const o = document.createElement("option"); o.value = k; o.textContent = k; sel.appendChild(o); });
  const fc = document.getElementById("filter");
  TYPES.forEach(t => { const o = document.createElement("option"); o.value = t; o.textContent = t; fc.appendChild(o); });
  fc.onchange = () => renderNotes(lastNotes);
  const lg = document.getElementById("legend");
  TYPES.forEach(t => { const b = document.createElement("span"); b.className = "badge t-" + t; b.textContent = t; lg.appendChild(b); });
  const stSel = document.getElementById("seltype");
  TYPES.forEach(t => { const o = document.createElement("option"); o.value = t; o.textContent = t; stSel.appendChild(o); });
  const files = await api("/api/files", { method: "GET" });
  const fs = document.getElementById("file");
  files.files.forEach(f => { const o = document.createElement("option"); o.value = f; o.textContent = f; fs.appendChild(o); });
  if (files.files.length) { fs.selectedIndex = 0; }
}
let lastNotes = [];
let selIndex = -1;
const TYPE_COLOR = { kick:"#ff8a8a", snare:"#6db3ff", floor:"#e8b35a", rack1:"#e8b35a", rack2:"#e8b35a", crash1:"#c9a0ff", crash2:"#c9a0ff", hat_closed:"#b8c0cc", hat_open:"#b8c0cc", ride:"#b8c0cc", ride_bell:"#b8c0cc" };
const LANE_H = 54, LBL_W = 112, AX_H = 28;

function laneTypes(notes) {
  const seen = [];
  for (const t of TYPES) if (notes.some(n => n.type === t)) seen.push(t);
  notes.forEach(n => { if (!seen.includes(n.type)) seen.push(n.type); });
  return seen;
}
function viewMetrics(shown) {
  let tMin = 0, tMax = shown.length ? Math.max(...shown.map(n => n.onset_s)) : 1;
  const pad = Math.max(0.5, tMax * 0.02); tMin = Math.max(0, tMin - pad); tMax += pad;
  const plotW = Math.max(200, document.getElementById("rollwrap").clientWidth - 4) - LBL_W - 14;
  return { tMin, tMax, pxPerSec: plotW / (tMax - tMin) };
}
function drawRoll() {
  const notes = lastNotes, filt = document.getElementById("filter").value;
  const shown = filt ? notes.filter(n => n.type === filt) : notes;
  document.getElementById("summary").textContent = `${shown.length} / ${notes.length} note events`;
  document.getElementById("export").disabled = false;
  const cvs = document.getElementById("roll");
  const W = Math.max(300, document.getElementById("rollwrap").clientWidth);
  const lanes = laneTypes(notes);
  cvs.width = W; cvs.height = lanes.length * LANE_H + AX_H;
  const ctx = cvs.getContext("2d");
  const m = viewMetrics(shown);
  // grid ticks
  ctx.font = "12px ui-monospace,Consolas,monospace";
  const step = [0.25, 0.5, 1, 2, 5].find(s => (m.tMax / s) <= 24) || 10;
  for (let tt = Math.ceil(m.tMin / step) * step; tt <= m.tMax + 1e-9; tt += step) {
    const x = LBL_W + (tt - m.tMin) * m.pxPerSec; if (x > W) break;
    ctx.strokeStyle = "#20252f"; ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, cvs.height - AX_H); ctx.stroke();
    ctx.fillStyle = "#77808f"; ctx.fillText(tt.toFixed(step < 1 ? 2 : 0), x + 3, cvs.height - 8);
  }
  lanes.forEach((t, i) => {
    const y = i * LANE_H;
    ctx.fillStyle = i % 2 ? "#151820" : "#12151d"; ctx.fillRect(LBL_W, y, W - LBL_W, LANE_H);
    ctx.fillStyle = "#c3cbd8"; ctx.font = "13px system-ui,sans-serif"; ctx.fillText(t, 10, y + LANE_H * 0.58);
    ctx.strokeStyle = "#222736"; ctx.strokeRect(LBL_W, y, W - LBL_W, LANE_H);
    shown.forEach(n => {
      if (n.type !== t) return;
      const x = LBL_W + (n.onset_s - m.tMin) * m.pxPerSec;
      const bw = Math.max(6, Math.min(18, 7 + n.velocity * 12));
      ctx.fillStyle = TYPE_COLOR[n.type] || "#888"; ctx.globalAlpha = 0.4 + 0.6 * n.velocity;
      ctx.fillRect(x, y + 9, bw, LANE_H - 18); ctx.globalAlpha = 1;
      if (notes.indexOf(n) === selIndex) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 2.5; ctx.strokeRect(x - 3, y + 6, bw + 6, LANE_H - 12); ctx.lineWidth = 1; }
    });
  });
}
function updatePanel() {
  const panel = document.getElementById("sel");
  if (selIndex < 0 || selIndex >= lastNotes.length) { panel.style.display = "none"; return; }
  const n = lastNotes[selIndex];
  document.getElementById("selinfo").textContent = `${n.type} @ ${n.onset_s.toFixed(3)}s · v=${n.velocity.toFixed(2)}`;
  document.getElementById("seltype").value = n.type;
  panel.style.display = "";
}
function selectNote(i) { selIndex = i; updatePanel(); drawRoll(); }
function onRollClick(ev) {
  const cvs = document.getElementById("roll");
  const r = cvs.getBoundingClientRect();
  const X = ev.clientX - r.left, Y = ev.clientY - r.top;
  const notes = lastNotes, filt = document.getElementById("filter").value;
  const shown = filt ? notes.filter(n => n.type === filt) : notes;
  const m = viewMetrics(shown);
  const lanes = laneTypes(notes);
  const lane = Math.floor(Y / LANE_H);
  if (lane < 0 || lane >= lanes.length) return;
  const type = lanes[lane];
  const tAt = (X - LBL_W) / m.pxPerSec + m.tMin;
  let best = -1, bd = 12 / m.pxPerSec;
  shown.forEach(n => { if (n.type !== type) return; const d = Math.abs(n.onset_s - tAt); if (d <= bd) { bd = d; best = notes.indexOf(n); } });
  selectNote(best);
}
function renderNotes(notes) { lastNotes = notes; drawRoll(); updatePanel(); }
async function edit(body) {
  const st = document.getElementById("status"); st.textContent = "editing…";
  try {
    const j = await api("/api/edit", { method: "POST", body: JSON.stringify(body) });
    if (selIndex >= j.notes.length) selIndex = j.notes.length - 1;
    renderNotes(j.notes); st.textContent = "done";
  } catch (e) { st.textContent = "error: " + e.message; }
}
async function run() {
  const btn = document.getElementById("run"); btn.disabled = true;
  const st = document.getElementById("status"); st.textContent = "processing…";
  try {
    const body = { file: document.getElementById("file").value,
                   kit: document.getElementById("kit").value,
                   method: document.getElementById("method").value };
    const j = await api("/api/run", { method: "POST", body: JSON.stringify(body) });
    renderNotes(j.notes);
    document.getElementById("results").style.display = "";
    st.textContent = "done";
  } catch (e) { st.textContent = "error: " + e.message; }
  finally { btn.disabled = false; }
}
async function exportMidi() {
  const btn = document.getElementById("export"); btn.disabled = true;
  const st = document.getElementById("status"); st.textContent = "exporting…";
  try {
    const body = { file: document.getElementById("file").value,
                   kit: document.getElementById("kit").value,
                   method: document.getElementById("method").value };
    const j = await api("/api/export", { method: "POST", body: JSON.stringify(body) });
    st.textContent = j.ok ? "exported → " + j.path : j.error;
  } catch (e) { st.textContent = "error: " + e.message; }
  finally { btn.disabled = false; }
}
async function upload() {
  const f = document.getElementById("upfile").files[0];
  if (!f) return;
  const st = document.getElementById("status"); st.textContent = "uploading " + f.name + "…";
  const r = await fetch("/api/upload?name=" + encodeURIComponent(f.name), {
    method: "POST",
    headers: { "X-Auth-Token": token, "Content-Type": "application/octet-stream" },
    body: f
  });
  const j = await r.json();
  if (!r.ok) { st.textContent = "upload error: " + (j.error || r.status); return; }
  st.textContent = "uploaded → " + j.file;
  const files = await api("/api/files", { method: "GET" });
  const fs = document.getElementById("file");
  fs.innerHTML = "";
  files.files.forEach(nm => { const o = document.createElement("option"); o.value = nm; o.textContent = nm; fs.appendChild(o); });
  if (files.files.length) { fs.value = j.file; }
}
document.getElementById("run").onclick = run;
document.getElementById("export").onclick = exportMidi;
document.getElementById("upbtn").onclick = upload;
document.getElementById("roll").addEventListener("click", onRollClick);
document.getElementById("mvL").onclick = () => { if (selIndex >= 0) edit({ action: "move", index: selIndex, delta_s: -0.01 }); };
document.getElementById("mvR").onclick = () => { if (selIndex >= 0) edit({ action: "move", index: selIndex, delta_s: 0.01 }); };
document.getElementById("seldel").onclick = () => { if (selIndex >= 0) edit({ action: "delete", index: selIndex }); };
document.getElementById("seltype").onchange = () => { if (selIndex >= 0) edit({ action: "reassign", index: selIndex, type: document.getElementById("seltype").value }); };
window.addEventListener("resize", () => { if (lastNotes.length) drawRoll(); });
init();
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "DrumMIDIWeb/1.0"

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
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
                               threshold_preset=body.get("preset", "tuned-mixwave"))
            self.server.notes = notes
            self.server.last_file = p
            self._json({"count": len(notes), "notes": notes})
        except Exception as e:  # surface real errors to the UI
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

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
