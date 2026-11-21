export function bindTransport({media,roll,keyboard=document,getBpm,onError,requestFrame=requestAnimationFrame,cancelFrame=cancelAnimationFrame}) {
  let frame=0;
  const sync=()=>roll.setAttribute('currenttime',String((Number.isFinite(media.currentTime)?media.currentTime:0)*getBpm()/60));
  function stop(){if(frame)cancelFrame(frame);frame=0;sync();}
  function tick(){frame=0;sync();if(!media.paused&&!media.ended)frame=requestFrame(tick);}
  const play=()=>{if(!frame)frame=requestFrame(tick);};
  for(const event of ['timeupdate','seeked','loadedmetadata','emptied'])media.addEventListener(event,sync);
  for(const event of ['pause','ended','error'])media.addEventListener(event,stop);
  media.addEventListener('play',play);
  keyboard.addEventListener('keydown',event=>{
    if(event.code!=='Space'||event.repeat||event.defaultPrevented||event.ctrlKey||event.altKey||event.metaKey||event.shiftKey)return;
    if(event.target.closest('input,select,textarea,button,a,audio,summary,[contenteditable]:not([contenteditable="false"]),[role="textbox"]'))return;
    if(!media.getAttribute('src'))return;
    event.preventDefault();
    if(media.paused)media.play().catch(error=>onError(error.message));else media.pause();
  },true);
  sync();
  return {sync,seek(beat){
    if(!media.getAttribute('src')||!Number.isFinite(media.duration)||!Number.isFinite(beat)){sync();return;}
    media.currentTime=Math.max(0,Math.min(media.duration,beat*60/getBpm()));sync();
  }};
}
