# Web UI (remote control)

```powershell
# from project folder
.venv\Scripts\python.exe -m drum_midi.webui --host 0.0.0.0 --port 8123 --dir PATH [--token X]
```

- Pure stdlib (`ThreadingHTTPServer`) — no flask/fastapi.
- Token required on all `/api` (`X-Auth-Token`, hmac.compare_digest); random if unset, printed at start for LAN.
- Endpoints: `GET /` (single-page HTML), `GET /api/files`, `GET /api/meta`, `POST /api/run`, `POST /api/edit`, `POST /api/export`, `POST /api/upload?name=<file>`.
- Piano-roll editor (canvas): lane per drum type, drag bar = retime, cross-lane drag = retype, zoom/pan (wheel + buttons), type filter. Select note → edit panel (reassign / ±10ms / del).
- Upload: raw audio bytes, sanitized name (`Path(name).name`), extension whitelist, Content-Length check.
