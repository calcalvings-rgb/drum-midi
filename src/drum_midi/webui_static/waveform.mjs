export const secondsToBeats = (seconds,bpm) => seconds*bpm/60;
export const secondsPerPixel = (pxPerBeat,bpm) => 60/(pxPerBeat*bpm);

export async function buildPeaks(channels,sampleRate,binsPerSecond=256) {
  if(!channels.length||!channels[0].length||!Number.isFinite(sampleRate)||sampleRate<=0)throw Error('Empty or invalid WAV audio');
  const frames=channels[0].length,duration=frames/sampleRate;
  const count=Math.ceil(duration*binsPerSecond);
  const min=new Float32Array(count),max=new Float32Array(count);
  let amplitude=0;
  for(let bin=0;bin<count;bin++) {
    const from=Math.floor(bin*sampleRate/binsPerSecond);
    const to=Math.min(frames,Math.max(from+1,Math.floor((bin+1)*sampleRate/binsPerSecond)));
    let low=0,high=0;
    for(const channel of channels)for(let frame=from;frame<to;frame++) {
      const value=channel[frame];if(!Number.isFinite(value))continue;
      if(value<low)low=value;if(value>high)high=value;
    }
    min[bin]=low;max[bin]=high;amplitude=Math.max(amplitude,-low,high);
    if(bin%4096===4095)await new Promise(resolve=>setTimeout(resolve,0));
  }
  return {min,max,amplitude,duration,sampleRate,binsPerSecond,channels:channels.length};
}
export async function decodeWav(file) {
  if(!/\.(wav|wave)$/i.test(file.name))throw Error('Choose a WAV file for the waveform reference.');
  if(file.size>256*1024*1024)throw Error('This prototype supports reference WAV files up to 256 MB.');
  const context=new OfflineAudioContext(1,1,48000);
  const audio=await context.decodeAudioData(await file.arrayBuffer());
  const channels=Array.from({length:audio.numberOfChannels},(_,i)=>audio.getChannelData(i));
  return buildPeaks(channels,audio.sampleRate);
}
export class WaveformOverlay {
  data=null;
  name='';
  bpm=120;
  frame=0;
  constructor(timewindow) {
    this.timewindow=timewindow;
    this.area=timewindow.querySelector('.gsuiTimewindow-scrollArea');
    this.content=timewindow.querySelector('.gsuiTimewindow-mainContent');
    this.canvas=document.createElement('canvas');
    this.canvas.className='waveform-reference';this.canvas.setAttribute('role','img');
    this.canvas.hidden=true;
    this.content.prepend(this.canvas);
    this.area.addEventListener('scroll',()=>this.request(),{passive:true});
    timewindow.addEventListener('gsui',()=>this.request(),true);
    this.resize=new ResizeObserver(()=>this.request());this.resize.observe(this.area);
  }
  setSource(data,name) {
    this.data=data;this.name=name;this.canvas.hidden=false;
    this.canvas.setAttribute('aria-label',`Waveform reference: ${name}, ${data.duration.toFixed(3)} seconds, display normalized. Starts at beat one, zero seconds.`);
    this.request();
  }
  clear() {this.data=null;this.name='';this.canvas.hidden=true;}
  setBpm(bpm) {if(this.bpm!==bpm){this.bpm=bpm;this.request();}}
  get durationBeats() {return this.data?secondsToBeats(this.data.duration,this.bpm):0;}
  request() {
    if(!this.frame)this.frame=requestAnimationFrame(()=>{this.frame=0;this.draw();});
  }
  draw() {
    if(!this.data)return;
    const area=this.area.getBoundingClientRect(),content=this.content.getBoundingClientRect();
    const panel=this.timewindow.querySelector('.gsuiTimewindow-panel').getBoundingClientRect();
    const timeline=this.timewindow.querySelector('.gsuiTimewindow-time').getBoundingClientRect();
    const down=this.timewindow.querySelector('.gsuiTimewindow-contentDown').getBoundingClientRect();
    const left=area.left+panel.width,top=area.top+timeline.height;
    const width=Math.max(0,Math.floor(this.area.clientWidth-panel.width));
    const height=Math.max(0,Math.floor(Math.min(area.top+this.area.clientHeight,down.top)-top));
    if(!width||!height)return;
    const origin=left-content.left;
    Object.assign(this.canvas.style,{left:`${origin}px`,top:`${top-content.top}px`,width:`${width}px`,height:`${height}px`});
    const dpr=Math.min(devicePixelRatio||1,2);
    this.canvas.width=Math.round(width*dpr);this.canvas.height=Math.round(height*dpr);
    const context=this.canvas.getContext('2d');context.setTransform(dpr,0,0,dpr,0,0);
    context.clearRect(0,0,width,height);
    const ppb=Number(this.timewindow.getAttribute('pxperbeat'));
    const seconds=secondsPerPixel(ppb,this.bpm);
    const data=this.data,rate=data.binsPerSecond,scale=height*.43/(data.amplitude||1),middle=height/2;
    context.strokeStyle='#9de3ce';context.lineWidth=1.25;
    context.beginPath();
    for(let x=0;x<width;x++) {
      const start=(origin+x)*seconds,end=(origin+x+1)*seconds;
      if(end<=0||start>=data.duration)continue;
      const a=Math.max(0,Math.floor(start*rate)),b=Math.min(data.max.length,Math.max(a+1,Math.ceil(end*rate)));
      let low=0,high=0;
      for(let i=a;i<b;i++){low=Math.min(low,data.min[i]);high=Math.max(high,data.max[i]);}
      context.moveTo(x+.5,middle-high*scale);context.lineTo(x+.5,middle-low*scale);
    }
    context.stroke();
    this.canvas.dataset.bpm=String(this.bpm);
    this.canvas.dataset.pxPerSecond=String(1/seconds);
    this.canvas.dataset.originPixels=String(origin);
    this.canvas.dataset.durationSeconds=String(data.duration);
  }
}
