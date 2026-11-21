import test from 'node:test';
import assert from 'node:assert/strict';
import {transcriptionToEditor, visibleNotes, visibleSelectedIds, requiresReplacementConfirmation} from '../src/drum_midi/webui_static/adapter.mjs';
import {EditorState} from '../src/drum_midi/webui_static/model.mjs';
const gm={kick:36,hat_closed:42,crash1:49};
test('setting tempo in an empty editor does not prompt to replace nonexistent notes',()=>{
 assert.equal(requiresReplacementConfirmation(true,0),false);
 assert.equal(requiresReplacementConfirmation(true,1),true);
 assert.equal(requiresReplacementConfirmation(false,100),false);
});
test('transcription seconds become beats at visible BPM without quantizing',()=>{
 const result=transcriptionToEditor([{type:'hat_closed',onset_s:.13,velocity:.7}],90,gm);
 assert.equal(result.notes[0].key,42);assert.equal(result.notes[0].when,.195);assert.equal(result.notes[0].gain,.7);
});
test('flattened cymbal is retained as crash with a visible warning',()=>{
 const result=transcriptionToEditor([{type:'cymbal',onset_s:1,velocity:.8}],120,gm);
 assert.equal(result.notes[0].key,49);assert.match(result.warning,/cymbal/i);
});
test('unknown types fail instead of silently dropping hits',()=>{
 assert.throws(()=>transcriptionToEditor([{type:'unknown',onset_s:1,velocity:.8}],120,gm),/unknown/);
});
test('visible-note filtering never changes the full editor take',()=>{
 const notes={a:{key:36,when:0},b:{key:42,when:1}};
 assert.deepEqual(Object.keys(visibleNotes(notes,'42')),['b']);assert.equal(Object.keys(notes).length,2);
});
test('single-note history stores a delta, not a full take snapshot',()=>{
 const model=new EditorState();model.load(Array.from({length:1000},(_,i)=>({key:36,when:i*.25,duration:.1,gain:.8})),120,'take');
 model.velocity(['0'],.5);
 assert.equal(model.past[0].changes.length,1);
 assert.ok(model.historyBytes<10000);
 model.undo();assert.equal(model.notes['0'].gain,.8);model.redo();assert.equal(model.notes['0'].gain,.5);
});
test('history is bounded and a new edit invalidates redo',()=>{
 const model=new EditorState();model.add(36,0,.25);
 for(let i=0;i<130;i++)model.velocity(['0'],i%2?.5:.9);
 assert.ok(model.past.length<=100);assert.ok(model.historyBytes<=16*1024*1024);
 model.undo();model.velocity(['0'],.3);assert.equal(model.future.length,0);
});

test('invalid edit rolls back rather than poisoning undo state',()=>{
 const model=new EditorState();model.add(36,0,.25);const before=JSON.stringify(model.snapshot());
 assert.throws(()=>model.move(['0'],NaN,0));assert.equal(JSON.stringify(model.snapshot()),before);
 assert.throws(()=>model.duplicate(['0'],100001));assert.equal(JSON.stringify(model.snapshot()),before);
});
test('oversized loads are rejected before replacing the current take',()=>{
 const model=new EditorState();model.add(36,0,.25);
 assert.throws(()=>model.load(Array(50001),120,'oversized'));
 assert.equal(Object.keys(model.notes).length,1);
});

test('undo cannot leave an invisible instrument selected behind a filter',()=>{
 const model=new EditorState();model.load([{key:36,when:0,duration:.25,gain:1},{key:42,when:1,duration:.25,gain:1}],120,'take');
 model.select(['0']);model.move(['0'],.25,0);model.select([]);model.undo();
 assert.deepEqual(visibleSelectedIds(model.notes,'42'),[]);
 assert.equal(Object.keys(model.notes).length,2);
});
