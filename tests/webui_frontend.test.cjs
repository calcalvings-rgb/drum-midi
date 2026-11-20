// Renderer unit tests. Browser integration is exercised against the real HTTP API.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

async function app(width = 286) {
  const labels = [];
  const ctx = new Proxy({}, { get: (o, k) => o[k] || (() => {}), set: (o, k, v) => (o[k] = v, true) });
  ctx.fillText = (text, x, y) => labels.push({ text, x, y });
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: '', checked: false, disabled: false, style: {}, dataset: {}, clientWidth: width,
      textContent: '', length: 0, width, height: 0,
      appendChild() {}, replaceChildren() {}, add() {}, addEventListener() {}, setAttribute() {},
      getContext: () => ctx,
      getBoundingClientRect() { return { left: 0, top: 0, width: this.width, height: this.height }; },
    });
    return elements.get(id);
  }
  const sandbox = vm.createContext({
    document: { getElementById: element, createElement: () => ({}), addEventListener() {} },
    window: { addEventListener() {} }, location: { search: '' }, URLSearchParams,
    Option: function(text, value) { this.text = text; this.value = value; },
    fetch: async url => ({ ok: true, json: async () => url === '/api/meta'
      ? { kits: ['gm'], types: ['kick', 'snare'], methods: ['trigger'] }
      : { files: [] } }),
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/drum_midi/webui_static/app.js'), 'utf8'), sandbox);
  await new Promise(setImmediate);
  return { sandbox, elements, labels };
}

test('canvas drawing uses the actual narrow container width', async () => {
  const { sandbox, elements } = await app(286);
  vm.runInContext('lastNotes = [{type:"kick",onset_s:1,velocity:.8}]; drawRoll();', sandbox);
  assert.equal(elements.get('roll').width, 286);
});

test('timeline labels stay at least 40 pixels apart in a narrow editor', async () => {
  const { sandbox, labels } = await app(356);
  vm.runInContext('lastNotes = [{type:"kick",onset_s:3,velocity:.8}]; drawRoll();', sandbox);
  const ticks = labels.filter(l => /^\d/.test(String(l.text)));
  assert.ok(ticks.length >= 2);
  for (let i = 1; i < ticks.length; i++) assert.ok(ticks[i].x - ticks[i-1].x >= 40);
});

test('startup with no recordings allows upload but not transcription', async () => {
  const { elements } = await app();
  assert.equal(elements.get('upbtn').disabled, false);
  assert.equal(elements.get('run').disabled, true);
  assert.equal(elements.get('export').disabled, true);
  assert.equal(elements.get('connection').dataset.ready, 'true');
});


test('a completed transcription with zero hits shows a useful empty state', async () => {
  const { sandbox, elements } = await app();
  vm.runInContext('hasResult = true; renderNotes([]);', sandbox);
  assert.equal(elements.get('results').style.display, 'none');
  assert.equal(elements.get('empty').style.display, '');
  assert.equal(elements.get('empty-heading').textContent, 'No hits detected');
  assert.match(elements.get('empty-description').textContent, /different engine/);
});


test('keyboard selects hits in the filtered timeline without a pointer', async () => {
  const { sandbox, elements } = await app();
  vm.runInContext('lastNotes = [{type:"kick",onset_s:1,velocity:.8},{type:"snare",onset_s:2,velocity:.7}]; hasResult = true; onRollKey({key:"ArrowDown", preventDefault(){}});', sandbox);
  assert.match(elements.get('selinfo').textContent, /kick/);
  vm.runInContext('onRollKey({key:"ArrowDown", preventDefault(){}});', sandbox);
  assert.match(elements.get('selinfo').textContent, /snare/);
  vm.runInContext('onRollKey({key:"Escape", preventDefault(){}});', sandbox);
  assert.equal(elements.get('sel').style.display, 'none');
  elements.get('filter').value = 'snare';
  vm.runInContext('onRollKey({key:"ArrowDown", preventDefault(){}});', sandbox);
  assert.match(elements.get('selinfo').textContent, /snare/);
});
