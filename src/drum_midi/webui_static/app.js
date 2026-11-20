
const token = new URLSearchParams(location.search).get("token") || "";
const TYPES = [];
let initialized = false, busy = false, hasResult = false;
function status(message, state = "ready") {
  const el = document.getElementById("status");
  el.textContent = message; el.dataset.state = state;
}
function syncControls() {
  for (const id of ["file", "kit", "method", "upbtn", "upfile", "groove", "flatten", "velsmooth", "protgrooves"]) {
    document.getElementById(id).disabled = !initialized || busy;
  }
  document.getElementById("run").disabled = !initialized || busy || !document.getElementById("file").value;
  document.getElementById("export").disabled = !hasResult || busy;
  for (const id of ["filter", "zin", "zout", "zfit", "seltype", "mvL", "mvR", "seldel"]) document.getElementById(id).disabled = busy;
  document.getElementById("workspace").setAttribute("aria-busy", String(busy));
}
function setBusy(value) { busy = value; syncControls(); }

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
  const methods = document.getElementById("method");
  methods.replaceChildren(...meta.methods.map(m => new Option(m, m)));
  methods.value = "trigger";
  const sel = document.getElementById("kit");
  meta.kits.forEach(k => { const o = document.createElement("option"); o.value = k; o.textContent = k; sel.appendChild(o); });
  const fc = document.getElementById("filter");
  TYPES.forEach(t => { const o = document.createElement("option"); o.value = t; o.textContent = t; fc.appendChild(o); });
  fc.onchange = () => { selIndex = -1; view = null; renderNotes(lastNotes); };
  const lg = document.getElementById("legend");
  TYPES.forEach(t => { const b = document.createElement("span"); b.className = "badge t-" + t; b.textContent = t; lg.appendChild(b); });
  const stSel = document.getElementById("seltype");
  TYPES.forEach(t => { const o = document.createElement("option"); o.value = t; o.textContent = t; stSel.appendChild(o); });
  const files = await api("/api/files", { method: "GET" });
  const fs = document.getElementById("file");
  files.files.forEach(f => { const o = document.createElement("option"); o.value = f; o.textContent = f; fs.appendChild(o); });
  fs.replaceChildren(...files.files.map(f => new Option(f, f)));
  if (!files.files.length) fs.add(new Option("No recordings yet. Upload audio to begin.", ""));
  initialized = true;
  syncControls();
  const connection = document.getElementById("connection");
  connection.textContent = "Engine connected"; connection.dataset.ready = "true";
  status(files.files.length ? "Ready when you are." : "Upload a recording to get started.");
}
let lastNotes = [];
let selIndex = -1;
let drag = null;
let view = null, pan = null, lastPps = 100, fullRng = 1;
const TYPE_COLOR = { kick:"#f58b62", snare:"#8dd6c2", floor:"#b7a4e8", rack1:"#b7a4e8", rack2:"#b7a4e8" };
const LANE_H = 54, LBL_W = 112, AX_H = 28;

function laneTypes(notes) {
  const seen = [];
  for (const t of TYPES) if (notes.some(n => n.type === t)) seen.push(t);
  notes.forEach(n => { if (!seen.includes(n.type)) seen.push(n.type); });
  return seen;
}
function fullView(shown) {
  let tMin = 0, tMax = shown.length ? Math.max(...shown.map(n => n.onset_s)) : 1;
  const pad = Math.max(0.5, tMax * 0.02); tMin = Math.max(0, tMin - pad); tMax += pad;
  return { start: tMin, dur: tMax - tMin };
}
function curView(shown) {
  const f = fullView(shown);
  if (!view) return f;
  const dur = Math.min(view.dur, f.dur);
  const start = Math.max(f.start, Math.min(view.start, f.start + f.dur - dur));
  return { start, dur };
}
function currentShown() {
  const filt = document.getElementById("filter").value;
  return filt ? lastNotes.filter(n => n.type === filt) : lastNotes;
}
function drawRoll() {
  const notes = lastNotes, shown = currentShown();
  document.getElementById("summary").textContent = `${shown.length} / ${notes.length} note events`;
  syncControls();
  const cvs = document.getElementById("roll");
  const W = Math.max(1, document.getElementById("rollwrap").clientWidth);
  const lanes = laneTypes(notes);
  cvs.width = W; cvs.height = lanes.length * LANE_H + AX_H;
  const ctx = cvs.getContext("2d"), v = curView(shown);
  fullRng = fullView(shown).dur;
  const cW = Math.max(1, W - LBL_W - 14);
  lastPps = cW / v.dur;
  ctx.fillStyle = "#131518"; ctx.fillRect(0, 0, W, cvs.height);
  lanes.forEach((type, i) => {
    const y = i * LANE_H;
    ctx.fillStyle = i % 2 ? "#1b1e24" : "#16181d";
    ctx.fillRect(LBL_W, y, W - LBL_W, LANE_H);
    ctx.fillStyle = "#e6e8ec"; ctx.font = "13px system-ui,sans-serif";
    ctx.fillText(type, 10, y + LANE_H * 0.58);
    ctx.strokeStyle = "#383d45"; ctx.strokeRect(LBL_W, y, W - LBL_W, LANE_H);
  });
  const targetStep = v.dur / Math.max(1, Math.floor(cW / 64));
  const magnitude = 10 ** Math.floor(Math.log10(targetStep));
  const step = [1, 2, 5, 10].map(s => s * magnitude).find(s => s >= targetStep);
  ctx.font = "12px ui-monospace,Consolas,monospace";
  for (let tt = Math.ceil(v.start / step) * step; tt <= v.start + v.dur + 1e-9; tt += step) {
    const x = LBL_W + (tt - v.start) * lastPps;
    ctx.strokeStyle = "#383d45"; ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, cvs.height - AX_H); ctx.stroke();
    if (x < W - 35) {
      ctx.fillStyle = "#b2b7c2";
      ctx.fillText(tt.toFixed(step < 0.25 ? 3 : step < 1 ? 2 : 0) + "s", x + 3, cvs.height - 8);
    }
  }
  ctx.save(); ctx.beginPath(); ctx.rect(LBL_W, 0, W - LBL_W, cvs.height - AX_H); ctx.clip();
  notes.forEach((n, index) => {
    if (!shown.includes(n)) return;
    const eff = drag && index === drag.idx ? drag : null;
    const type = eff ? eff.curType : n.type, onset = eff ? eff.curOnset : n.onset_s;
    const lane = lanes.indexOf(type);
    if (lane < 0) return;
    const x = LBL_W + (onset - v.start) * lastPps, y = lane * LANE_H;
    const width = Math.max(6, Math.min(18, 7 + n.velocity * 12));
    ctx.fillStyle = TYPE_COLOR[type] || "#c9cbd1";
    ctx.globalAlpha = 0.65 + 0.35 * n.velocity;
    ctx.fillRect(x, y + 9, width, LANE_H - 18); ctx.globalAlpha = 1;
    if (index === selIndex) {
      ctx.strokeStyle = "#f1f0ed"; ctx.lineWidth = 2.5;
      ctx.strokeRect(x - 3, y + 6, width + 6, LANE_H - 12); ctx.lineWidth = 1;
    }
  });
  ctx.restore();
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
function onRollKey(event) {
  if (busy || !hasResult) return;
  const keys = ["ArrowDown", "ArrowUp", "Home", "End", "Enter", "ArrowLeft", "ArrowRight", "Delete", "Backspace", "Escape"];
  if (!keys.includes(event.key)) return;
  event.preventDefault();
  if (event.key === "Escape") { selectNote(-1); return; }
  const shown = currentShown();
  const indices = shown.map(n => lastNotes.indexOf(n)).sort((a, b) => lastNotes[a].onset_s - lastNotes[b].onset_s);
  if (!indices.length) return;
  const pos = indices.indexOf(selIndex);
  if (["ArrowDown", "ArrowUp", "Home", "End", "Enter"].includes(event.key)) {
    let next = pos < 0 ? 0 : pos;
    if (event.key === "ArrowDown") next = Math.min(pos + 1, indices.length - 1);
    if (event.key === "ArrowUp") next = pos < 0 ? indices.length - 1 : Math.max(0, pos - 1);
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = indices.length - 1;
    selectNote(indices[next]); return;
  }
  if (pos < 0) return;
  if (["Delete", "Backspace"].includes(event.key)) edit({ action: "delete", index: selIndex });
  else edit({ action: "move", index: selIndex, delta_s: event.key === "ArrowLeft" ? -0.01 : 0.01 });
}

function noteAt(ev) {
  const cvs = document.getElementById("roll");
  const r = cvs.getBoundingClientRect();
  const X = ev.clientX - r.left, Y = ev.clientY - r.top;
  const shown = currentShown();
  const v = curView(shown);
  const lanes = laneTypes(lastNotes);
  const lane = Math.floor(Y / LANE_H);
  if (lane < 0 || lane >= lanes.length) return null;
  const type = lanes[lane];
  const tAt = v.start + (X - LBL_W) / lastPps;
  let best = -1, bd = 14 / lastPps;
  shown.forEach(n => { if (n.type !== type) return; const d = Math.abs(n.onset_s - tAt); if (d <= bd) { bd = d; best = lastNotes.indexOf(n); } });
  if (best < 0) return null;
  return { idx: best, n: lastNotes[best] };
}
function setView(s, d) {
  const f = fullView(currentShown());
  if (d >= f.dur - 1e-6) { view = null; return; }
  const nd = Math.max(0.05, Math.min(d, f.dur));
  const ns = Math.max(f.start, Math.min(s, f.start + f.dur - nd));
  view = { start: ns, dur: nd };
}
function zoomBy(factor) {
  const shown = currentShown();
  const v = curView(shown);
  const cvs = document.getElementById("roll");
  const cx = cvs.width / 2;
  const nd = v.dur * factor;
  const tAt = v.start + (cx - LBL_W) / lastPps;
  setView(tAt - (cx - LBL_W) * (nd / (cvs.width - LBL_W - 14)), nd);
  drawRoll();
}
function onDown(ev) {
  if (busy || !hasResult) return;
  document.getElementById("roll").focus({ preventScroll: true });
  const hit = noteAt(ev);
  if (!hit) {
    const v = curView(currentShown());
    if (view && v.dur < fullRng - 1e-6) { pan = { startX: ev.clientX, view: { start: v.start, dur: v.dur } }; ev.preventDefault(); return; }
    selectNote(-1); return;
  }
  drag = { idx: hit.idx, origOnset: hit.n.onset_s, origType: hit.n.type, curOnset: hit.n.onset_s, curType: hit.n.type };
  selectNote(hit.idx);
  ev.preventDefault();
}
function onMove(ev) {
  if (pan) {
    const v = curView(currentShown());
    const dx = (ev.clientX - pan.startX) / lastPps;
    setView(pan.view.start - dx, pan.view.dur);
    drawRoll();
    return;
  }
  if (!drag) return;
  const X = ev.clientX, Y = ev.clientY;
  const cvs = document.getElementById("roll");
  const r = cvs.getBoundingClientRect();
  const v = curView(currentShown());
  const lanes = laneTypes(lastNotes);
  drag.curOnset = Math.max(0, v.start + (X - r.left - LBL_W) / lastPps);
  const lane = Math.floor((Y - r.top) / LANE_H);
  if (lane >= 0 && lane < lanes.length) drag.curType = lanes[lane];
  drawRoll();
}
async function onUp() {
  if (pan) { pan = null; return; }
  if (!drag) return;
  const d = drag; drag = null;
  try {
    if (d.curType !== d.origType && !await edit({ action: "reassign", index: d.idx, type: d.curType })) return;
    if (Math.abs(d.curOnset - d.origOnset) > 0.0001) await edit({ action: "move", index: d.idx, delta_s: d.curOnset - d.origOnset });
    else selectNote(d.idx);
  } catch (e) { document.getElementById("status").textContent = "error: " + e.message; }
}
function renderNotes(notes) {
  lastNotes = notes;
  document.getElementById("results").style.display = notes.length ? "" : "none";
  document.getElementById("empty").style.display = notes.length ? "none" : "";
  if (!notes.length && hasResult) {
    document.getElementById("empty-heading").textContent = "No hits detected";
    document.getElementById("empty-description").textContent = "Try a different engine or another recording, then transcribe again.";
  }
  drawRoll(); updatePanel();
}
async function edit(body) {
  setBusy(true); status("Updating selected hit…", "busy");
  try {
    const j = await api("/api/edit", { method: "POST", body: JSON.stringify(body) });
    if (selIndex >= j.notes.length) selIndex = j.notes.length - 1;
    renderNotes(j.notes); status("Hit updated."); return true;
  } catch (e) { status("Could not update hit: " + e.message, "error"); return false; }
  finally { setBusy(false); }
}
async function run() {
  if (busy || !document.getElementById("file").value) return;
  setBusy(true); status("Transcribing audio… this may take a moment.", "busy");
  try {
    const body = { file: document.getElementById("file").value,
                   kit: document.getElementById("kit").value,
                   method: document.getElementById("method").value,
                   groove: document.getElementById("groove").checked,
                   flatten_cymbal: document.getElementById("flatten").checked,
                   velocity_smooth: document.getElementById("velsmooth").checked,
                   protect_grooves: document.getElementById("protgrooves").checked };
    const j = await api("/api/run", { method: "POST", body: JSON.stringify(body) });
    hasResult = true; selIndex = -1; view = null; drag = null; pan = null;
    document.getElementById("take-name").textContent = body.file;
    renderNotes(j.notes);
    status(j.notes.length ? `${j.notes.length} hits ready. Select a hit to refine it.` : "No hits detected. Try a different engine or recording.");
  } catch (e) { status("Transcription failed: " + e.message, "error"); }
  finally { setBusy(false); }
}
async function exportMidi() {
  if (busy || !hasResult) return;
  setBusy(true); status("Writing MIDI…", "busy");
  try {
    const body = { file: document.getElementById("file").value, kit: document.getElementById("kit").value, method: document.getElementById("method").value };
    const j = await api("/api/export", { method: "POST", body: JSON.stringify(body) });
    status(j.ok ? "Saved on the engine computer: " + j.path : j.error, j.ok ? "ready" : "error");
  } catch (e) { status("Export failed: " + e.message, "error"); }
  finally { setBusy(false); }
}
async function upload() {
  const f = document.getElementById("upfile").files[0];
  if (!f || busy) { if (!f) status("Choose a recording to upload first."); return; }
  setBusy(true); status("Uploading " + f.name + "…", "busy");
  try {
    const r = await fetch("/api/upload?name=" + encodeURIComponent(f.name), { method: "POST", headers: { "X-Auth-Token": token, "Content-Type": "application/octet-stream" }, body: f });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || r.status);
    const files = await api("/api/files", { method: "GET" });
    const fs = document.getElementById("file");
    fs.replaceChildren(...files.files.map(name => new Option(name, name))); fs.value = j.file;
    status("Uploaded " + j.file + ". Ready to transcribe.");
  } catch (e) { status("Upload failed: " + e.message, "error"); }
  finally { setBusy(false); }
}
document.getElementById("run").onclick = run;
document.getElementById("export").onclick = exportMidi;
document.getElementById("upbtn").onclick = upload;
document.getElementById("roll").addEventListener("mousedown", onDown);
document.getElementById("roll").addEventListener("keydown", onRollKey);
document.addEventListener("mousemove", onMove);
document.addEventListener("mouseup", onUp);
document.getElementById("roll").addEventListener("wheel", e => { e.preventDefault(); zoomBy(e.deltaY > 0 ? 1.25 : 0.8); }, { passive: false });
document.getElementById("zin").onclick = () => zoomBy(0.7);
document.getElementById("zout").onclick = () => zoomBy(1.4);
document.getElementById("zfit").onclick = () => { view = null; drawRoll(); };
document.getElementById("roll").addEventListener("touchstart", e => { e.preventDefault(); const t = e.touches[0]; onDown({ clientX: t.clientX, clientY: t.clientY, preventDefault() {} }); }, { passive: false });
document.addEventListener("touchmove", e => { const t = e.touches[0]; if (t) onMove({ clientX: t.clientX, clientY: t.clientY }); }, { passive: true });
document.addEventListener("touchend", onUp);
document.getElementById("mvL").onclick = () => { if (selIndex >= 0) edit({ action: "move", index: selIndex, delta_s: -0.01 }); };
document.getElementById("mvR").onclick = () => { if (selIndex >= 0) edit({ action: "move", index: selIndex, delta_s: 0.01 }); };
document.getElementById("seldel").onclick = () => { if (selIndex >= 0) edit({ action: "delete", index: selIndex }); };
document.getElementById("seltype").onchange = () => { if (selIndex >= 0) edit({ action: "reassign", index: selIndex, type: document.getElementById("seltype").value }); };
window.addEventListener("resize", () => { if (hasResult) drawRoll(); });
if (typeof ResizeObserver !== "undefined") new ResizeObserver(() => { if (hasResult) drawRoll(); }).observe(document.getElementById("rollwrap"));
document.getElementById("file").onchange = syncControls;
init().catch(e => {
  document.getElementById("connection").textContent = "Engine unavailable";
  status("Connection failed: " + e.message + ". Check the token in this page URL, then reload.", "error");
});
