
import { EditorState, snapStep } from './model.mjs';
import { decodeWav, WaveformOverlay } from './waveform.mjs';
import { installFileDrop } from './dropzone.mjs';
import { bindTransport } from './transport.mjs';
import { exportSnapshot, transcriptionToEditor, visibleNotes, visibleSelectedIds, requiresReplacementConfirmation } from './adapter.mjs';

const model = new EditorState();
const el = id => document.getElementById(id);
const drumNames = {35:'Ac. kick',36:'Kick',37:'Side stick',38:'Snare',39:'Clap',40:'E. snare',41:'Low tom',42:'Closed hat',43:'Floor tom',44:'Pedal hat',45:'Low-mid tom',46:'Open hat',47:'Rack tom',48:'Hi-mid tom',49:'Crash',50:'High tom',51:'Ride',52:'China',53:'Ride bell',54:'Tambourine',55:'Splash',56:'Cowbell',57:'Crash 2',59:'Ride 2'};
let token = '', renderedIds = [], roll, timewindow, waveform, dirty = false, savedSignature = '';
let midiLoading=false,wavLoading=false,dropLoading=false,processing=false,sourceLoading=false,filesLoading=false;
let localAudio=null,uploadedAudio=null,sourceEpoch=0,gmMap={},playbackUrl='',transport;
function signature() {
  return JSON.stringify({bpm:model.bpm,notes:Object.values(model.notes).map(({key,when,duration,gain})=>({key,when,duration,gain})).sort((a,b)=>a.when-b.when||a.key-b.key||a.duration-b.duration||a.gain-b.gain)});
}
function mayReplace() {
  return !requiresReplacementConfirmation(dirty,Object.keys(model.notes).length) || confirm('Replace the current take? Unexported edits will be lost. Export MIDI first to keep them.');
}
function setPxPerBeat(value) {
  value=Math.round(value);
  timewindow.$setAttr('pxperbeat',value).$dispatch(GSEV_TIMEWINDOW_PXPERBEAT,value);
}
function focusNotes() {
  requestAnimationFrame(()=>{
    const area=timewindow.querySelector('.gsuiTimewindow-scrollArea');
    const topPitch=Math.max(36,...Object.values(model.notes).map(n=>n.key));
    const rowHeight=Number(timewindow.getAttribute('lineheight'));
    area.scrollTo({left:0,top:Math.max(0,(131-topPitch-2)*rowHeight),behavior:'instant'});
  });
}
function status(message, state='ready') {el('status').textContent=message;el('status').dataset.state=state;}
function setPlayback(file=null) {
  const player=el('wav-player');
  player.pause();player.removeAttribute('src');
  if(playbackUrl)URL.revokeObjectURL(playbackUrl);
  playbackUrl=file?URL.createObjectURL(file):'';
  player.hidden=!file;
  if(file)player.src=playbackUrl;
  player.load();
}
function syncImportControls() {
  const busy=midiLoading||wavLoading||dropLoading||processing||sourceLoading||filesLoading;
  for(const id of ['midi','wav','drop-browse','drop-files'])el(id).disabled=busy||!token;
  el('clear-wave').disabled=busy||!waveform?.data;
  for(const id of ['file','refresh-files','method','preset','groove','flatten','velsmooth','protgrooves'])el(id).disabled=busy||!token;
  el('bpm').disabled=processing;
  el('run').disabled=busy||(!localAudio&&!el('file').value);
  el('drop-zone').dataset.busy=String(busy);
  el('drop-zone').setAttribute('aria-busy',String(busy));
}
function dropFeedback(message,state='ready') {
  el('drop-status').textContent=message;el('drop-status').dataset.state=state;
}
function apply(operation) {
  try {operation();render();status(model.lastAction+'. Edits are local until export.');}
  catch(error) {render();status(error.message,'error');}
}
function ui() {
  const selected=model.selected();
  el('undo').disabled=!model.past.length;
  el('redo').disabled=!model.future.length;
  for (const id of ['delete','duplicate','quantize','velocity']) el(id).disabled=!selected.length;
  el('quantize').disabled=!selected.length||el('snap').value==='off';
  el('export').disabled=!Object.keys(model.notes).length;
  el('take-name').textContent=model.name;
  el('summary').textContent=`${renderedIds.length} / ${Object.keys(model.notes).length} hits · ${selected.length} selected · ${model.past.length} undo steps`;
  el('selection').textContent=selected.length?`${selected.length} selected`:'No hits selected';
  if(selected.length) {
    const value=Math.max(1,Math.round(model.notes[selected[0]].gain*127));
    el('velocity').value=value;el('velocity-value').textContent=value;
  }
  el('bpm').value=Number(model.bpm.toFixed(3));
}
function selectionDOM() {
  for (const id of renderedIds) {
    const n=model.notes[id];
    roll.$changeKeyProp(id,'selected',n.selected);
    const block=roll.querySelector(`.gsuiPianoroll-block[data-id="${id}"]`);
    if(block)block.setAttribute('aria-selected',String(n.selected));
  }
  ui();
}
function extentBeats() {return Math.max(8,waveform?.durationBeats||0,...Object.values(model.notes).map(n=>n.when+n.duration));}
function render() {
  if(!roll)return;
  for(const id of renderedIds)roll.$removeKey(id);
  const shown=visibleNotes(model.notes,el('filter').value);
  model.select(visibleSelectedIds(model.notes,el('filter').value));
  roll.$setData(shown);
  renderedIds=Object.keys(shown);
  for(const [id,n] of Object.entries(shown)) {
    const block=roll.$addKey(id,n).$get(0);
    const label=drumNames[n.key]||`MIDI ${n.key}`;
    block.querySelector('span').textContent=label;
    block.id=`note-${id}`;block.setAttribute('role','option');
    block.setAttribute('aria-selected',String(n.selected));
    block.setAttribute('aria-label',`${label}, beat ${n.when.toFixed(3)}, length ${n.duration.toFixed(3)}, velocity ${Math.round(n.gain*127)}`);
    block.title=block.getAttribute('aria-label');
  }
  if(waveform)waveform.setBpm(model.bpm);
  transport?.sync();
  for(const note of Object.values(model.notes))if(![...el('filter').options].some(o=>o.value===String(note.key)))el('filter').add(new Option(drumNames[note.key]||`MIDI ${note.key}`,String(note.key)));
  const end=extentBeats();
  roll.$changeDuration(Math.ceil(end/4)*4);
  dirty=signature()!==savedSignature;
  ui();
}
function change(action,...args) {
  if(action==='selection') {args[0].forEach(id=>{if(model.notes[id])model.notes[id].selected=true;});selectionDOM();return;}
  if(action==='unselection') {model.select([]);selectionDOM();return;}
  if(action==='unselectionOne') {if(model.notes[args[0]])model.notes[args[0]].selected=false;selectionDOM();return;}
  apply(()=>{
    if(action==='add')model.add(...args);
    else if(action==='move')model.move(args[0],args[1],-args[2]);
    else if(action==='cropEnd')model.crop(...args);
    else if(action==='remove')model.remove(...args);
    else if(action==='clone')model.duplicate(...args);
    else throw Error(`This prototype does not support ${action}`);
  });
}
function setSnap() {
  const step=snapStep(el('snap').value);
  timewindow.querySelector('gsui-step-select').removeAttribute('auto');
  timewindow.setAttribute('step',String(step*4));
  ui();status(el('snap').value==='off'?'Snap off. Imported timing stays intact.':`Snap ${el('snap').value}. Use Quantize selected to align existing hits.`);
}
function load(notes,bpm,name) {
  model.load(notes,bpm,name);el('filter').value='';savedSignature=signature();render();focusNotes();
}
function duplicate() {
  const ids=model.selected(),ns=ids.map(id=>model.notes[id]);if(!ns.length)return;
  const step=snapStep(el('snap').value);
  const start=Math.min(...ns.map(n=>n.when)),end=Math.max(...ns.map(n=>n.when+n.duration));
  const offset=Math.max(step,Math.ceil((end-start)/step)*step);
  apply(()=>model.duplicate(ids,offset));roll.focus({preventScroll:true});
}
async function request(path,body,type='application/json') {
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':type,'X-Auth-Token':token},body});
  if(!response.ok){const data=await response.json();throw Error(data.error||'Request failed');}
  return response;
}
async function importMidi(file) {
  if(!file)return false;
  if(!mayReplace()){el('midi').value='';status('MIDI import canceled. Current take was kept.');return false;}
  const before=signature();
  midiLoading=true;syncImportControls();status('Reading MIDI note events…');
  try {
    const response=await request('/api/editor/import',file,'audio/midi');
    const data=await response.json();
    if(signature()!==before&&!mayReplace()){status('MIDI import canceled. Current take was kept.');return false;}
    load(data.notes,data.bpm,file.name);
    status(`Imported ${data.notes.length} hits. ${data.warning}`);
    return true;
  }catch(error){status(error.message,'error');return false;}
  finally{midiLoading=false;el('midi').value='';syncImportControls();}
}
async function importReferenceWav(file,{engine=false,peaks:stagedPeaks=null}={}) {
  if(!file)return false;
  wavLoading=true;syncImportControls();
  status('Decoding WAV locally and preparing waveform…');
  try {
    const peaks=stagedPeaks||await decodeWav(file);
    setPlayback(file);
    waveform.setSource(peaks,file.name);waveform.setBpm(model.bpm);
    if(!engine){localAudio=file;uploadedAudio=null;el('file').value='';sourceEpoch++;el('audio-source').textContent=`Local WAV: ${file.name}. Transcription sends it to this engine.`;}
    el('wave-info').textContent=`${file.name} · ${peaks.duration.toFixed(3)}s · display normalized · starts at 0s`;
    render();el('fit').click();
    status('WAV reference loaded locally. It follows tempo, zoom and scroll and is not included in MIDI export.');
    return true;
  }catch(error){status('Could not load WAV: '+error.message,'error');return false;}
  finally{wavLoading=false;el('wav').value='';syncImportControls();}
}
async function exportMidi() {
  const exportedSignature=signature();
  el('export').disabled=true;status('Creating MIDI download…');
  try {
    const response=await request('/api/editor/export',JSON.stringify(exportSnapshot(model,el('kit').value)));
    const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');
    a.href=url;a.download='grooveforge-edited.mid';a.click();
    setTimeout(()=>URL.revokeObjectURL(url),5000);savedSignature=exportedSignature;dirty=signature()!==savedSignature;
    status('MIDI download created. The WAV reference is not included.');
  }catch(error){status(error.message,'error');}
  finally{ui();}
}
async function jsonGet(path) {
  const response=await fetch(path,{headers:{'X-Auth-Token':token}});
  const value=await response.json();
  if(!response.ok)throw Error(value.error||'Engine request failed');
  return value;
}
async function refreshFiles(prefer='') {
  if(filesLoading)return;
  filesLoading=true;syncImportControls();
  try {
    const result=await jsonGet('/api/files');
    const selected=prefer||el('file').value;
    el('file').replaceChildren(new Option(localAudio?`Local WAV: ${localAudio.name}`:'Choose engine audio or load a local WAV',''),...result.files.map(name=>new Option(name,name)));
    if(result.files.includes(selected))el('file').value=selected;
  }finally{filesLoading=false;syncImportControls();}
}
async function chooseEngineAudio() {
  const name=el('file').value,epoch=++sourceEpoch;
  localAudio=null;uploadedAudio=null;waveform.clear();setPlayback();
  el('wave-info').textContent='No waveform loaded.';
  el('audio-source').textContent=name?`Engine audio: ${name}`:'Load a local WAV or choose engine audio.';
  if(!name){syncImportControls();return;}
  sourceLoading=true;syncImportControls();
  try {
    if(!/\.(wav|wave)$/i.test(name)) {
      status('Engine audio selected. Waveform preview requires WAV; other codecs require ffmpeg for transcription.');return;
    }
    status('Loading the WAV reference from this engine…');
    const response=await fetch('/api/audio?file='+encodeURIComponent(name),{headers:{'X-Auth-Token':token}});
    if(!response.ok){const error=await response.json();throw Error(error.error||'Could not load engine audio');}
    const audio=new File([await response.blob()],name,{type:'audio/wav'});
    if(epoch!==sourceEpoch)return;
    await importReferenceWav(audio,{engine:true});
  }catch(error){status(error.message,'error');}
  finally{sourceLoading=false;syncImportControls();}
}
async function transcribeSource() {
  if(processing||sourceLoading||filesLoading||midiLoading||wavLoading||dropLoading)return;
  if(!localAudio&&!el('file').value){status('Choose engine audio or load a WAV first.','error');return;}
  if(!mayReplace()){status('Transcription canceled. Current edits were kept.');return;}
  const before=signature(),bpm=model.bpm,local=localAudio;
  processing=true;syncImportControls();
  try {
    let filename=el('file').value;
    if(local) {
      if(uploadedAudio?.file===local)filename=uploadedAudio.name;
      else {
        status('Uploading WAV to this local/LAN engine…');
        const upload=await(await request('/api/upload?name='+encodeURIComponent(local.name),local,'application/octet-stream')).json();
        filename=upload.file;uploadedAudio={file:local,name:filename};
        await refreshFiles(filename);
        el('audio-source').textContent=`Local WAV ${local.name}, on engine as ${filename}`;
      }
    }
    status('Transcribing audio on this engine…');
    const body={file:filename,method:el('method').value,preset:el('preset').value,
      groove:el('groove').checked,flatten_cymbal:el('flatten').checked,
      velocity_smooth:el('velsmooth').checked,protect_grooves:el('protgrooves').checked};
    const result=await(await request('/api/run',JSON.stringify(body))).json();
    const converted=transcriptionToEditor(result.notes,bpm,gmMap);
    if(signature()!==before&&!mayReplace()){status('Transcription result discarded; newer edits were kept.');return;}
    el('filter').value='';load(converted.notes,bpm,filename);
    status(converted.notes.length?`${converted.notes.length} hits ready. ${converted.warning}`:'No hits detected. Try another engine or threshold preset.');
  }catch(error){status('Transcription failed: '+error.message,'error');}
  finally{processing=false;syncImportControls();}
}

async function importDroppedFiles({midi,wav}) {
      dropLoading=true;syncImportControls();dropFeedback('Loading files…','busy');
      try {
        const peaks=midi&&wav?await decodeWav(wav):null;
        if(midi&&!await importMidi(midi)){dropFeedback(el('status').textContent,el('status').dataset.state);return;}
        if(wav&&!await importReferenceWav(wav,{peaks})){dropFeedback(el('status').textContent,'error');return;}
        dropFeedback(`Loaded ${[midi?.name,wav?.name].filter(Boolean).join(' + ')}.`);
      }catch(error){status('Import failed: '+error.message,'error');dropFeedback(el('status').textContent,'error');}
      finally{dropLoading=false;syncImportControls();}
}

async function init() {
  const incoming=new URLSearchParams(location.search).get('token');
  try {
    token=incoming||sessionStorage.getItem('grooveforge-token')||'';
    if(incoming){sessionStorage.setItem('grooveforge-token',incoming);history.replaceState(null,'',location.pathname+location.hash);}
  }catch{token=incoming||'';}
  const response=await fetch('/api/meta',{headers:{'X-Auth-Token':token}});
  if(!response.ok)throw Error('Engine connection failed. Open this page using the token URL printed by the server.');
  const meta=await response.json();gmMap=meta.gm_map;
  if(!gmMap)throw Error('Engine metadata is missing GM mappings');
  el('method').replaceChildren(...meta.methods.map(x=>new Option(x,x)));el('method').value='trigger';
  el('preset').replaceChildren(...meta.presets.map(x=>new Option(x,x)));el('preset').value='tuned-mixwave';
  el('kit').replaceChildren(...meta.kits.map(x=>new Option(x,x)));el('kit').disabled=false;
  for(const [type,pitch] of Object.entries(gmMap)){
    drumNames[pitch]=type.replaceAll('_',' ');
    el('filter').add(new Option(drumNames[pitch],String(pitch)));
  }
  const Roll=customElements.get('gsui-pianoroll');
  if(!Roll)throw Error('GridSound component did not load');
  Roll.$keyNotation('CDEFGAB');gsuiKeys.$keyNotation('CDEFGAB');gsuiTimeline.$numbering(1);
  roll=document.createElement('gsui-pianoroll');roll.id='editor';roll.setAttribute('tabindex','0');
  roll.setAttribute('role','listbox');roll.setAttribute('aria-multiselectable','true');
  roll.setAttribute('aria-label','Drum MIDI notes. Ctrl A selects all. Arrows move selected hits. Delete removes. Ctrl Z undoes.');
  el('mount').append(roll);
  roll.$setCallbacks(change);roll.$setData(model.notes);roll.$octaves(0,11);roll.$timedivision('4/4');
  timewindow=roll.querySelector('gsui-timewindow');
  waveform=new WaveformOverlay(timewindow);
  transport=bindTransport({media:el('wav-player'),roll,getBpm:()=>model.bpm,onError:message=>status(message,'error')});
  timewindow.$setAttr('lineheight',24).$dispatch(GSEV_TIMEWINDOW_LINEHEIGHT,24);setPxPerBeat(88);
  const props=roll.querySelector('gsui-prop-select');props.setAttribute('props','gain:Velocity');
  props.querySelector('button').setAttribute('aria-label','Velocity lane');
  props.querySelector('button').disabled=true;
  roll.querySelector('gsui-slidergroup').setAttribute('aria-label','Velocity lane; the range below is its keyboard alternative.');
  roll.querySelector('gsui-slidergroup').$options({min:1/127,max:1,step:1/127,def:.8});
  for(const key of roll.querySelectorAll('gsui-keys [data-midi]')) {
    const label=drumNames[Number(key.dataset.midi)];if(label)key.dataset.drum=label;
  }
  roll.addEventListener('gsui',event=>{
    const d=event.detail;
    if(d.$event===GSEV_TIMELINE_CHANGECURRENTTIME)transport.seek(Number(d.$args[0]));
    if(d.$event===GSEV_PIANOROLL_CHANGEKEYSPROPS) {
      const [prop,entries]=d.$args;
      if(prop==='gain')apply(()=>model.properties(entries));
    }
  });
  roll.addEventListener('pointerdown',event=>{
    const block=event.target.closest('.gsuiPianoroll-block');
    if(event.button===0&&block&&!event.shiftKey&&!event.ctrlKey&&!model.notes[block.dataset.id]?.selected) {
      model.select([block.dataset.id]);selectionDOM();
    }
  },true);
  roll.addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Escape'].includes(event.key))return;
    event.preventDefault();event.stopPropagation();
    if(event.key==='Escape'){model.select([]);selectionDOM();return;}
    const ids=model.selected();
    if(!ids.length){const first=renderedIds[0];if(first){model.select([first]);selectionDOM();}return;}
    const step=snapStep(el('snap').value);
    if(event.key==='ArrowLeft'||event.key==='ArrowRight')apply(()=>model.move(ids,event.key==='ArrowLeft'?-step:step,0));
    else apply(()=>model.move(ids,0,event.key==='ArrowUp'?1:-1));
  });
  document.addEventListener('keydown',event=>{
    if(event.target.closest('input,select,textarea,[contenteditable=true]'))return;
    const key=event.key.toLowerCase();
    if(!(event.ctrlKey||event.metaKey)||!['z','y'].includes(key))return;
    event.preventDefault();event.stopPropagation();
    apply(()=>key==='y'||event.shiftKey?model.redo():model.undo());
  },true);
  el('undo').onclick=()=>apply(()=>model.undo());el('redo').onclick=()=>apply(()=>model.redo());
  el('snap').onchange=setSnap;
  el('bpm').onchange=()=>apply(()=>model.setTempo(Number(el('bpm').value)));
  el('select-all').onclick=()=>{model.select(renderedIds);selectionDOM();roll.focus({preventScroll:true});};
  el('quantize').onclick=()=>apply(()=>model.quantize(model.selected(),snapStep(el('snap').value)));
  el('duplicate').onclick=duplicate;el('delete').onclick=()=>apply(()=>model.remove(model.selected()));
  el('velocity').oninput=()=>{el('velocity-value').textContent=el('velocity').value;};
  el('velocity').onchange=()=>apply(()=>model.velocity(model.selected(),Number(el('velocity').value)/127));
  el('midi').onchange=async()=>{
    const file=el('midi').files[0];if(!file)return;
    dropFeedback('Loading MIDI…','busy');
    await importMidi(file);
    dropFeedback(el('status').textContent,el('status').dataset.state);
  };
  el('wav').onchange=async()=>{
    const file=el('wav').files[0];if(!file)return;
    dropFeedback('Loading WAV…','busy');
    await importReferenceWav(file);
    dropFeedback(el('status').textContent,el('status').dataset.state);
  };
  el('clear-wave').onclick=()=>{
    waveform.clear();setPlayback();el('clear-wave').disabled=true;
    el('wave-info').textContent='No waveform loaded. Audio starts at 0 seconds / beat 1.';
    render();status('Waveform reference cleared. MIDI hits were not changed.');
  };
  el('wav-player').addEventListener('error',()=>{if(playbackUrl)status('Browser cannot play this WAV encoding. Convert to PCM WAV for playback.','error');});
  window.addEventListener('pagehide',()=>setPlayback());
  el('export').onclick=exportMidi;
  el('filter').onchange=()=>{model.select([]);render();};
  el('file').onchange=chooseEngineAudio;el('refresh-files').onclick=()=>refreshFiles().catch(e=>status(e.message,'error'));
  el('run').onclick=transcribeSource;
  for(const [id,factor] of [['zoom-out',.8],['zoom-in',1.25]])el(id).onclick=()=>{
    const current=Number(timewindow.getAttribute('pxperbeat'));setPxPerBeat(Math.max(16,Math.min(200,current*factor)));
  };
  el('fit').onclick=()=>{
    const end=extentBeats();
    setPxPerBeat(Math.max(16,Math.min(200,(el('stage').clientWidth-170)/end)));
    focusNotes();
  };
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  savedSignature=signature();render();setSnap();await refreshFiles();status('Engine connected. Load WAV to transcribe, or open GM drum MIDI to edit.');
  installFileDrop({
    zone:el('drop-zone'),picker:el('drop-files'),browse:el('drop-browse'),
    isBusy:()=>midiLoading||wavLoading||dropLoading||processing||sourceLoading||filesLoading,
    onError:message=>{dropFeedback(message,'error');status(message,'error');},
    onImport:importDroppedFiles,
  });
  syncImportControls();

}
init().catch(error=>{status('Editor failed to start: '+error.message,'error');console.error(error);});
