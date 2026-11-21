import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// Execute the application's actual drop callback; stub I/O, never its ordering.
const source=fs.readFileSync(new URL('../src/drum_midi/webui_static/app.js',import.meta.url),'utf8');
const start=source.indexOf('async function importDroppedFiles(');
const end=source.indexOf('\nasync function init()',start);
function setup(badWave=false,cancel=false) {
 const state={take:'old.mid',wave:'old.wav',history:['move'],events:[],busy:false};
 const elements={status:{textContent:'',dataset:{}}};
 const context=vm.createContext({
  dropLoading:false,decodeWav:async()=>{state.events.push('decode');if(badWave)throw Error('corrupt WAV');return {duration:2};},
  syncImportControls:()=>{},dropFeedback:()=>{},el:id=>elements[id],status:(text)=>{elements.status.textContent=text;},
  importMidi:async()=>{state.events.push('midi');if(cancel)return false;state.take='new.mid';state.history=[];return true;},
  importReferenceWav:async()=>{state.events.push('wave');state.wave='new.wav';return true;},
 });
 vm.runInContext(source.slice(start,end),context);
 return {state,run:()=>vm.runInContext("importDroppedFiles({midi:{name:'new.mid'},wav:{name:'new.wav'}})",context)};
}
test('corrupt paired WAV cannot replace dirty MIDI or its history/reference',async()=>{
 const {state,run}=setup(true);await run();
 assert.equal(state.take,'old.mid');assert.deepEqual(state.history,['move']);assert.equal(state.wave,'old.wav');
 assert.deepEqual(state.events,['decode']);
});
test('canceling staged pair never commits waveform',async()=>{
 const {state,run}=setup(false,true);await run();
 assert.equal(state.take,'old.mid');assert.equal(state.wave,'old.wav');assert.deepEqual(state.events,['decode','midi']);
});
test('valid pair stages decoding then commits MIDI and reference',async()=>{
 const {state,run}=setup();await run();
 assert.equal(state.take,'new.mid');assert.equal(state.wave,'new.wav');assert.deepEqual(state.events,['decode','midi','wave']);
});
