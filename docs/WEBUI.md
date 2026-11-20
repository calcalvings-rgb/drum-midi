# Web UI (remote control)

```powershell
.venv\Scripts\python.exe -m drum_midi.webui --host 0.0.0.0 --port 8123 --dir PATH --token YOUR_TOKEN
```

Open `http://ENGINE_IP:8123/?token=YOUR_TOKEN` in the browser. The page forwards the query token as `X-Auth-Token` on API requests. Keep that URL private. Use a trusted network; the built-in server does not provide TLS.

- The Python server uses stdlib `ThreadingHTTPServer`. No frontend framework, npm install, Node runtime or build step is needed.
- `src/drum_midi/webui_static/` contains `index.html`, `app.js` (an ES module) and `style.css`. The server serves only those named public assets. Every `/api/*` route retains token authentication.
- The dark workspace keeps audio/upload/engine/kit/cleanup settings together, with a wider note editor. Settings reflow into two groups at medium widths and stack on phones.
- Transcribe a recording, then drag a hit horizontally to retime it or across an existing lane to reassign it. Select a hit for instrument reassignment, 10ms nudges or deletion. Use the filter, zoom controls, wheel zoom and empty-space drag to inspect the timeline.
- Keyboard in the timeline: Up/Down selects hits in time order, Home/End selects first/last, Left/Right nudges by 10ms, Delete/Backspace removes, and Escape deselects. The instrument selector also works with the keyboard.
- Exports save the last transcribed take as a `.mid` beside its recording on the engine computer, not to the remote browser's Downloads folder.
- Empty, working and failure states are written as text. The UI prevents overlapping operations from its own controls. The backend still has one shared note session; do not edit from multiple clients simultaneously.
- Uploads send raw audio bytes. The existing backend checks the extension and content length and strips path components from the submitted name.
- API endpoints remain `GET /api/files`, `GET /api/meta`, `POST /api/run`, `POST /api/edit`, `POST /api/export` and `POST /api/upload?name=<file>`.

## Desktop

Install `requirements-gui.txt` into the main venv, then run `drum_midi.py`. Sun Valley supplies native ttk dark styling. The canvas uses readable dark colors and supports Up/Down selection, Left/Right nudging and Delete. If the theme package is absent, the app warns and uses a dark clam fallback. Transcription remains synchronous; the status and disabled action indicate that the backend is working.
