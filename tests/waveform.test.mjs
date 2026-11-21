import test from 'node:test';
import assert from 'node:assert/strict';
import { buildPeaks, secondsToBeats, secondsPerPixel } from '../src/drum_midi/webui_static/waveform.mjs';

test('peak extraction preserves a known transient and source duration', async()=>{
  const samples=new Float32Array(1000);
  samples[500]=.8;samples[501]=-.6;
  const peaks=await buildPeaks([samples],1000,100);
  assert.equal(peaks.duration,1);
  assert.equal(peaks.max.length,100);
  assert.ok(Math.abs(peaks.max[50]-.8)<.000001);
  assert.ok(Math.abs(peaks.min[50]+.6)<.000001);
  assert.equal(peaks.max[49],0);
  assert.equal(peaks.min[51],0);
});
test('stereo peaks include both channels rather than cancelling them', async()=>{
  const left=new Float32Array([.7,0,-.5,0]);
  const right=new Float32Array([-.9,0,.8,0]);
  const peaks=await buildPeaks([left,right],4,2);
  assert.ok(peaks.min[0]<-.89);
  assert.ok(peaks.max[0]>.69);
});
test('waveform time follows BPM and zoom while seconds stay unchanged',()=>{
  assert.equal(secondsToBeats(.5,120),1);
  assert.equal(secondsToBeats(.5,60),.5);
  assert.equal(secondsPerPixel(200,120),.0025);
  assert.equal(secondsPerPixel(100,120),.005);
});
