export function transcriptionToEditor(notes,bpm,gm) {
  if(!Array.isArray(notes)||notes.length>50000||!Number.isFinite(bpm)||bpm<20||bpm>400)throw Error('Invalid transcription result or BPM');
  let flattened=false;
  const result=notes.map(note=>{
    let type=note.type;
    if(type==='cymbal'){type='crash1';flattened=true;}
    const key=gm[type];
    if(!Number.isInteger(key))throw Error(`Unsupported drum type: ${type}`);
    if(!Number.isFinite(note.onset_s)||note.onset_s<0||!Number.isFinite(note.velocity)||note.velocity<0)throw Error('Invalid transcription timing or velocity');
    const gain=note.velocity<=1?note.velocity:note.velocity/127;
    if(gain>1)throw Error('Invalid transcription velocity');
    return {key,when:note.onset_s*bpm/60,duration:.125,gain};
  });
  return {notes:result,warning:flattened?'Flattened cymbals are shown in the crash lane.':''};
}
export function requiresReplacementConfirmation(dirty,noteCount) { return dirty && noteCount > 0; }
export function visibleNotes(notes,pitch) {
  return pitch===''?notes:Object.fromEntries(Object.entries(notes).filter(([,note])=>note.key===Number(pitch)));
}
