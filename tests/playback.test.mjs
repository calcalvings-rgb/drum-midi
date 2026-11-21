import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../src/drum_midi/webui_static/app.js',import.meta.url),'utf8');
function fixture(){
 const events=[],player={hidden:true,src:'',pause(){events.push('pause');},removeAttribute(name){delete this[name];},load(){events.push('load');}};
 const context=vm.createContext({Blob,playbackUrl:'',el:()=>player,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:value=>events.push(value)}});
 const start=source.indexOf('function setPlayback('),end=source.indexOf('\nfunction syncImportControls',start);
 assert.ok(start>=0,'Application must manage playback URL lifetime');
 vm.runInContext(source.slice(start,end),context);
 return {context,player,events};
}
test('WAV attaches to native player without autoplay',async()=>{
 const {context,player,events}=fixture();await vm.runInContext('setPlayback({arrayBuffer:async()=>new ArrayBuffer(2)})',context);
 assert.equal(player.src,'blob:test');assert.equal(player.hidden,false);assert.deepEqual(events,['pause','load']);
});
test('replacing and clearing a WAV releases its URL and stops playback',async()=>{
 const {context,player,events}=fixture();await vm.runInContext('(async()=>{const f={arrayBuffer:async()=>new ArrayBuffer(2)};await setPlayback(f);await setPlayback(f);await setPlayback();})()',context);
 assert.equal(player.hidden,true);assert.equal(player.src,undefined);
 assert.equal(events.filter(value=>value==='blob:test').length,2);
});
