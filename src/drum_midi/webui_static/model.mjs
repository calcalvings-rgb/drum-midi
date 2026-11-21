export function snapStep(value) {
  if (value === 'off') return .000001;
  const denominator = Number(String(value).split('/')[1]);
  if (![4, 8, 16, 32, 64].includes(denominator)) throw new Error('Unsupported snap grid');
  return 4 / denominator;
}
const clone = value => structuredClone(value);
const fix = value => Number(value.toFixed(9));
const content = note => {if(!note)return null;const {selected,...value}=note;return value;};
const metadata = state => ({bpm:state.bpm,name:state.name,serial:state.serial,selected:Object.keys(state.notes).filter(id=>state.notes[id].selected)});
function number(value, min, max, name) {
  if (!Number.isFinite(value) || value < min || value > max) throw new Error(`Invalid ${name}`);
  return value;
}
export function makeNote(key, when, duration, gain = .8) {
  number(key, 0, 127, 'MIDI pitch');
  if (!Number.isInteger(key)) throw new Error('MIDI pitch must be an integer');
  return { key, when: number(when, 0, 100000, 'beat'), duration: number(duration, .000001, 100000, 'duration'),
    gain: number(gain, 0, 1, 'velocity'), selected: false, pan: 0, lowpass: 1, highpass: 1,
    gainLFOSpeed: 1, gainLFOAmp: 0, detuneLFOSpeed: 1, detuneLFOAmp: 0, prev: null, next: null };
}
export class EditorState {
  notes = {};
  bpm = 120;
  name = 'Untitled';
  past = [];
  future = [];
  serial = 0;
  lastAction = 'Ready';
  get historyBytes() {return [...this.past,...this.future].reduce((size,item)=>size+item.bytes,0);}
  selected() { return Object.keys(this.notes).filter(id => this.notes[id].selected); }
  snapshot() { return clone({notes:this.notes,bpm:this.bpm,name:this.name,serial:this.serial}); }
  restore(state) { Object.assign(this, clone(state)); }
  load(notes, bpm, name) {
    if(!Array.isArray(notes)||notes.length>50000)throw Error("At most 50000 notes are supported");
    const next = {};
    number(bpm, 20, 400, 'BPM');
    notes.forEach((n, i) => { next[String(i)] = makeNote(n.key, n.when, n.duration, n.gain); });
    this.notes = next; this.bpm = bpm; this.name = name; this.serial = notes.length;
    this.past = []; this.future = []; this.lastAction = 'Loaded recording';
  }
  change(label, operation) {
    const before=this.snapshot();
    const changes=[];
    try {
      operation();
      if(Object.keys(this.notes).length>50000)throw Error('At most 50000 notes are supported');
      for(const id of new Set([...Object.keys(before.notes),...Object.keys(this.notes)])) {
        const previous=content(before.notes[id]),next=content(this.notes[id]);
        if(JSON.stringify(previous)!==JSON.stringify(next)) {
          if(next)makeNote(next.key,next.when,next.duration,next.gain);
          changes.push([id,previous,next]);
        }
      }
    }catch(error){this.restore(before);throw error;}

    if(!changes.length&&before.bpm===this.bpm&&before.name===this.name&&before.serial===this.serial)return false;
    const entry={label,changes,before:metadata(before),after:metadata(this)};
    entry.bytes=JSON.stringify(entry).length*2;
    this.past.push(entry);this.future=[];
    while(this.past.length>1&&(this.past.length>100||this.historyBytes>16*1024*1024))this.past.shift();
    this.lastAction=label;return true;
  }
  applyHistory(entry,direction) {
    const index=direction==='before'?1:2;
    for(const change of entry.changes) {
      if(change[index]===null)delete this.notes[change[0]];
      else this.notes[change[0]]={...change[index],selected:false};
    }
    const {selected,...state}=entry[direction];Object.assign(this,state);this.select(selected);
  }
  select(ids, append = false) {
    const selected = new Set(ids);
    Object.entries(this.notes).forEach(([id,n]) => {n.selected = selected.has(id) || (append && n.selected);});
  }
  add(key, when, duration) {
    return this.change('Add hit', () => {
      const n=makeNote(key,when,duration); this.select([]); n.selected=true;
      this.notes[String(this.serial++)]=n;
    });
  }
  move(ids, beats, rows) {
    return this.change('Move hits', () => {
      const ns=ids.map(id=>this.notes[id]).filter(Boolean);if (!ns.length) return;
      const dt=Math.max(-Math.min(...ns.map(n=>n.when)),beats);
      const dk=Math.max(-Math.min(...ns.map(n=>n.key)),Math.min(127-Math.max(...ns.map(n=>n.key)),rows));
      ns.forEach(n=>{n.when=fix(n.when+dt);n.key+=dk;});
    });
  }
  crop(ids, delta) {
    return this.change('Resize hits', () => {
      const ns=ids.map(id=>this.notes[id]).filter(Boolean);
      const d=Math.max(.000001-Math.min(...ns.map(n=>n.duration)),delta);
      ns.forEach(n=>{n.duration=fix(n.duration+d);});
    });
  }
  remove(ids) { return this.change('Delete hits',()=>ids.forEach(id=>delete this.notes[id])); }
  duplicate(ids, offset) {
    return this.change('Duplicate hits',()=>{
      const ns=ids.map(id=>this.notes[id]).filter(Boolean).map(clone);
      this.select([]);
      ns.forEach(n=>{n.when=fix(n.when+offset);n.selected=true;this.notes[String(this.serial++)]=n;});
    });
  }
  quantize(ids, step) {
    return this.change('Quantize hits',()=>ids.forEach(id=>{const n=this.notes[id];if(n)n.when=fix(Math.max(0,Math.round(n.when/step)*step));}));
  }
  velocity(ids, value) {
    return this.change('Change velocity',()=>{
      number(value,0,1,'velocity');ids.forEach(id=>{if(this.notes[id])this.notes[id].gain=value;});
    });
  }
  properties(entries) {
    return this.change('Change velocity',()=>entries.forEach(([id,value])=>{
      number(value,0,1,'velocity');if(this.notes[id])this.notes[id].gain=value;
    }));
  }
  setTempo(value) {return this.change('Change tempo',()=>{this.bpm=number(value,20,400,'BPM');});}
  undo() {
    const item=this.past.pop();if (!item)return false;
    this.future.push(item);this.applyHistory(item,'before');
    this.lastAction='Undo: '+item.label;return true;
  }
  redo() {
    const item=this.future.pop();if (!item)return false;
    this.past.push(item);this.applyHistory(item,'after');
    this.lastAction='Redo: '+item.label;return true;
  }
}
