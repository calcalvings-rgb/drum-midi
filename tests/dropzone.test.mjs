import test from 'node:test';
import assert from 'node:assert/strict';
import { classifyDroppedFiles } from '../src/drum_midi/webui_static/dropzone.mjs';
const file=(name,size=100)=>({name,size});

test('routes MIDI to the note importer',()=>{
  const midi=file('take.mid');
  assert.deepEqual(classifyDroppedFiles([midi]),{midi,wav:null});
});
test('routes WAV to the local waveform loader',()=>{
  const wav=file('take.wav');
  assert.deepEqual(classifyDroppedFiles([wav]),{midi:null,wav});
});
test('accepts a MIDI and WAV pair regardless of file order or extension case',()=>{
  const midi=file('TAKE.MIDI'),wav=file('TAKE.WAVE');
  assert.deepEqual(classifyDroppedFiles([wav,midi]),{midi,wav});
});
test('rejects duplicate MIDI files instead of silently choosing one',()=>{
  assert.throws(()=>classifyDroppedFiles([file('a.mid'),file('b.midi')]),/one MIDI/i);
});
test('rejects duplicate WAV files instead of silently replacing the reference',()=>{
  assert.throws(()=>classifyDroppedFiles([file('a.wav'),file('b.wave')]),/one WAV/i);
});
test('rejects an unsupported mixed batch before returning any imports',()=>{
  assert.throws(()=>classifyDroppedFiles([file('a.mid'),file('song.mp3')]),/MIDI.*WAV/i);
});
test('rejects empty and oversized files before reading or uploading them',()=>{
  assert.throws(()=>classifyDroppedFiles([]),/MIDI.*WAV/i);
  assert.throws(()=>classifyDroppedFiles([file('empty.mid',0)]),/empty/i);
  assert.throws(()=>classifyDroppedFiles([file('big.mid',8*1024*1024+1)]),/8 MB/);
  assert.throws(()=>classifyDroppedFiles([file('big.wav',256*1024*1024+1)]),/256 MB/);
});
