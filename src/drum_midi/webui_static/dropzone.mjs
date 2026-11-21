export function classifyDroppedFiles(files) {
  const result={midi:null,wav:null};
  if(!files.length)throw Error('Drop a MIDI or WAV file, or one of each.');
  for(const file of files) {
    const name=String(file.name||'');
    const kind=/\.(mid|midi)$/i.test(name)?'midi':/\.(wav|wave)$/i.test(name)?'wav':null;
    if(!kind)throw Error('Only MIDI (.mid/.midi) and WAV (.wav/.wave) files are supported.');
    if(result[kind])throw Error(`Use only one ${kind==='midi'?'MIDI':'WAV'} file per drop.`);
    if(!Number.isFinite(file.size)||file.size<=0)throw Error(`${name} is empty or cannot be read.`);
    const limit=(kind==='midi'?8:256)*1024*1024;
    if(file.size>limit)throw Error(`${kind==='midi'?'MIDI':'WAV'} files must be ${kind==='midi'?8:256} MB or smaller.`);
    result[kind]=file;
  }
  return result;
}

export function installFileDrop({zone,picker,browse,isBusy,onImport,onError}) {
  const isFileDrag=event=>Array.from(event.dataTransfer?.types||[]).includes('Files')||!!event.dataTransfer?.files.length;
  const reset=()=>{zone.dataset.dragging='false';};
  async function load(files) {
    if(isBusy()){onError('An import is already in progress. Wait for it to finish.');return;}
    try {await onImport(classifyDroppedFiles(Array.from(files)));}
    catch(error){onError(error.message);}
  }
  browse.addEventListener('click',()=>picker.click());
  picker.addEventListener('change',async()=>{
    if(!picker.files.length)return;
    try{await load(picker.files);}finally{picker.value='';}
  });
  for(const name of ['dragenter','dragover'])zone.addEventListener(name,event=>{
    if(isFileDrag(event))zone.dataset.dragging=isBusy()?'false':'true';
  });
  zone.addEventListener('dragleave',event=>{
    if(!(event.relatedTarget instanceof Node)||!zone.contains(event.relatedTarget))reset();
  });
  window.addEventListener('dragover',event=>{
    if(!isFileDrag(event))return;
    event.preventDefault();
    event.dataTransfer.dropEffect=zone.contains(event.target)&&!isBusy()?'copy':'none';
  },true);
  window.addEventListener('drop',event=>{
    if(!isFileDrag(event))return;
    event.preventDefault();event.stopImmediatePropagation();reset();
    if(!zone.contains(event.target)){onError('Drop files in the import area above the editor.');return;}
    if(Array.from(event.dataTransfer.items||[]).some(item=>item.webkitGetAsEntry?.()?.isDirectory)){
      onError('Folders are not supported. Drop a MIDI or WAV file.');return;
    }
    void load(event.dataTransfer.files);
  },true);
  window.addEventListener('dragend',reset);
}
