export type SoundCue='intro'|'select'|'correct'|'incorrect'|'timeout'|'tick';
export type AudioPlayer=Pick<HTMLAudioElement,'play'|'pause'|'currentTime'|'volume'|'loop'|'onended'|'onerror'|'preload'>;
// A new URL also replaces copies of the previous synthesized sounds in browser caches.
export const audioUrl=(name:string)=>`/audio/${name}.wav?v=Yzhau6No0KY-1`;

/** Actual local WAV playback; nonverbal background never disables voice commands. */
export class QuizSoundtrack{
  private enabled=true;
  private activeQuestion=false;
  private microphone=false;
  private media=false;
  private speech=false;
  private bed:AudioPlayer|null=null;
  private foreground:AudioPlayer|null=null;
  private finishCue:(()=>void)|null=null;
  private cueTimer:ReturnType<typeof setTimeout>|null=null;
  constructor(private create:(url:string)=>AudioPlayer){}
  setEnabled(enabled:boolean){this.enabled=enabled;if(!enabled)this.stopCue();this.syncBed();}
  setQuestionActive(active:boolean){this.activeQuestion=active;this.syncBed();}
  setMediaActive(active:boolean){this.media=active;this.syncBed();}
  setMicrophoneActive(active:boolean){this.microphone=active;this.syncBed();}
  setSpeechActive(active:boolean){this.speech=active;this.syncBed();}
  private syncBed(){
    if(!this.enabled||!this.activeQuestion||this.microphone||this.speech||this.media){this.bed?.pause();return;}
    try{
      if(!this.bed){this.bed=this.create(audioUrl('suspense'));this.bed.loop=true;this.bed.volume=.18;this.bed.preload='auto';}
      void this.bed.play().catch(()=>{});
    }catch{/* audio optional; browser may need another user gesture */}
  }
  stopCue(){
    if(this.cueTimer)clearTimeout(this.cueTimer);this.cueTimer=null;
    if(this.foreground){this.foreground.onended=null;this.foreground.onerror=null;this.foreground.pause();this.foreground=null;}
    const finish=this.finishCue;this.finishCue=null;finish?.();
  }
  playCue(cue:SoundCue):Promise<void>{
    if(!this.enabled)return Promise.resolve();
    if((cue==='tick'||cue==='select')&&(this.microphone||this.speech||this.media))return Promise.resolve();
    this.stopCue();
    return new Promise(resolve=>{
      try{
        const audio=this.create(audioUrl(cue));this.foreground=audio;audio.volume=cue==='tick'?.35:.75;audio.preload='auto';
        const finish=()=>{
          if(this.foreground!==audio){resolve();return;}
          if(this.cueTimer)clearTimeout(this.cueTimer);this.cueTimer=null;audio.onended=null;audio.onerror=null;audio.pause();this.foreground=null;this.finishCue=null;resolve();
        };
        this.finishCue=finish;audio.onended=finish;audio.onerror=finish;
        this.cueTimer=setTimeout(finish,10000);
        void audio.play().catch(finish);
      }catch{resolve();}
    });
  }
}
export const soundtrack=new QuizSoundtrack(url=>new Audio(url));
