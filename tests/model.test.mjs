import test from 'node:test';
import assert from 'node:assert/strict';
import { EditorState, snapStep } from '../src/drum_midi/webui_static/model.mjs';

test('sixteenth and eighth note grids use beats, not seconds', () => {
  assert.equal(snapStep('1/16'), .25);
  assert.equal(snapStep('1/8'), .5);
  assert.equal(snapStep('1/4'), 1);
  assert.equal(snapStep('off'), .000001);
});
test('a grouped move is undone and redone atomically', () => {
  const m = new EditorState();
  m.load([{key:36,when:.13,duration:.25,gain:.8},{key:38,when:1.13,duration:.25,gain:.6}],120,'test');
  const ids = Object.keys(m.notes);
  m.select(ids);
  m.move(ids,.5,0);
  assert.deepEqual(Object.values(m.notes).map(n=>n.when),[.63,1.63]);
  assert.equal(m.past.length,1);
  m.undo();
  assert.deepEqual(Object.values(m.notes).map(n=>n.when),[.13,1.13]);
  m.redo();
  assert.deepEqual(Object.values(m.notes).map(n=>n.when),[.63,1.63]);
});
test('quantize is explicit and snap does not rewrite loaded microtiming', () => {
  const m = new EditorState();
  m.load([{key:36,when:.13,duration:.25,gain:.8}],120,'test');
  const [id]=Object.keys(m.notes);
  assert.equal(m.notes[id].when,.13);
  m.quantize([id],.25);
  assert.equal(m.notes[id].when,.25);
  m.undo();
  assert.equal(m.notes[id].when,.13);
});
test('new edit after undo invalidates redo', () => {
  const m = new EditorState();
  m.add(36,0,.25);m.add(38,1,.25);m.undo();
  m.add(42,2,.25);
  assert.equal(m.future.length,0);
  assert.equal(Object.keys(m.notes).length,2);
});
test('velocity, deletion and duplication are history entries', () => {
  const m = new EditorState();m.add(36,0,.25);
  const [id]=Object.keys(m.notes);
  m.velocity([id],.5);assert.equal(m.notes[id].gain,.5);
  m.duplicate([id],1);assert.equal(Object.keys(m.notes).length,2);
  m.undo();assert.equal(Object.keys(m.notes).length,1);
  m.remove([id]);assert.equal(Object.keys(m.notes).length,0);
  m.undo();assert.equal(m.notes[id].gain,.5);
});
test('grouped moves clamp as a group at beat zero and MIDI pitch bounds', () => {
  const m = new EditorState();
  m.load([{key:36,when:.2,duration:.25,gain:.8},{key:38,when:1.2,duration:.25,gain:.6}],120,'test');
  m.move(Object.keys(m.notes),-2,0);
  assert.deepEqual(Object.values(m.notes).map(n=>n.when),[0,1]);
});
