import {playPartyVoice,stopPartyVoice} from './partyVoice';
import {soundtrack,type SoundCue} from './soundtrack';
export type Announcement='camera-on'|'microphone-on'|'correct'|'incorrect'|'timeout'|'round-start';
type Style='notice'|'result'|'question';
type Synthesis=Pick<SpeechSynthesis,'getVoices'|'speak'|'cancel'>;
type Environment={playNotice?:(text:string)=>Promise<boolean>;stopNotice?:()=>void;readQuestions?:()=>boolean;engine:()=>Synthesis|null;utterance:(text:string)=>SpeechSynthesisUtterance;readEnabled?:()=>boolean;saveEnabled?:(enabled:boolean)=>void;playCue?:(cue:SoundCue)=>Promise<void>;stopCue?:()=>void;playbackChange?:(active:boolean)=>void;enabledChange?:(enabled:boolean)=>void};
type Job={text:string;style:Style;cue?:SoundCue;pauseMs:number};
const phrases:Record<Announcement,string>={'camera-on':'Камера включена.','microphone-on':'Микрофон включён.',correct:'Ответ верный!',incorrect:'Ответ неверный.',timeout:'Время вышло.', 'round-start':'Битва начинается!'};

/** Shared queue keeps speech recognition paused through playback and its echo tail. */
export class QuizAnnouncer{
  private queue:Job[]=[];
  private current:SpeechSynthesisUtterance|null=null;
  private generation=0;
  private timer:ReturnType<typeof setTimeout>|null=null;
  private watchdog:ReturnType<typeof setTimeout>|null=null;
  private blocking=false;
  private busy=false;
  private listeners=new Set<()=>void>();
  private playbackListeners=new Set<(active:boolean)=>void>();
  private snapshot:{enabled:boolean;message:string};
  constructor(private environment:Environment){let enabled=true;try{enabled=environment.readEnabled?.()??true;}catch{/* storage unavailable */}this.snapshot={enabled,message:enabled?'Голосовые уведомления готовы':'Голосовые уведомления выключены'};}
  getSnapshot=()=>this.snapshot;
  subscribe=(listener:()=>void)=>{this.listeners.add(listener);return()=>{this.listeners.delete(listener);};};
  onPlaybackChange(listener:(active:boolean)=>void){this.playbackListeners.add(listener);return()=>{this.playbackListeners.delete(listener);};}
  get isBlocking(){return this.blocking;}
  private message(message:string){this.snapshot={...this.snapshot,message};this.listeners.forEach(listener=>listener());}
  private setBlocking(active:boolean){if(this.blocking===active)return;this.blocking=active;this.environment.playbackChange?.(active);this.playbackListeners.forEach(listener=>listener(active));}
  setEnabled(enabled:boolean){
    this.snapshot={...this.snapshot,enabled};try{this.environment.saveEnabled?.(enabled);}catch{/* optional preference */}
    if(!enabled)this.cancel();this.environment.enabledChange?.(enabled);this.message(enabled?'Звук игры включён':'Звук игры выключен');
  }
  announce(event:Announcement,{pauseMs=350}:{pauseMs?:number}={}){const cue:SoundCue|undefined=event==='round-start'?'intro':['correct','incorrect','timeout'].includes(event)?event as SoundCue:undefined;return this.say(phrases[event],event==='correct'||event==='incorrect'||event==='timeout'?'result':'notice',cue,pauseMs);}
  say(text:string,style:Style='question',cue?:SoundCue,pauseMs=350){
    if(!this.snapshot.enabled||!text.trim()||(style==='question'&&this.environment.readQuestions?.()===false))return false;
    try{if(!this.environment.engine()&&!this.environment.playNotice&&!(cue&&this.environment.playCue)){this.message('Озвучка недоступна в этом браузере');return false;}}
    catch{this.message('Не удалось запустить озвучку');return false;}
    if(!this.busy&&this.timer){clearTimeout(this.timer);this.timer=null;}
    this.queue.push({text,style,cue,pauseMs});this.setBlocking(true);if(!this.busy)this.next();return true;
  }
  cancel(){
    this.generation++;this.queue=[];this.busy=false;
    if(this.timer)clearTimeout(this.timer);if(this.watchdog)clearTimeout(this.watchdog);
    this.timer=null;this.watchdog=null;
    this.environment.stopCue?.();this.environment.stopNotice?.();
    if(this.current){this.current.onend=null;this.current.onerror=null;this.current=null;}
    try{this.environment.engine()?.cancel();}catch{/* browser already stopped */}
    this.releaseAfterTail();
  }
  private releaseAfterTail(){
    if(!this.blocking)return;
    this.timer=setTimeout(()=>{this.timer=null;this.setBlocking(false);},600);
  }
  private next(){
    const job=this.queue.shift();
    if(!job){this.busy=false;this.releaseAfterTail();return;}
    this.busy=true;const generation=this.generation;
    this.message(job.style==='result'?'Озвучиваем результат…':job.text);
    const speak=async()=>{
      this.timer=null;if(generation!==this.generation)return;
      try{
        if(job.cue&&this.environment.playCue)await this.environment.playCue(job.cue);
        if(generation!==this.generation)return;
        if(job.style!=='question'&&this.environment.playNotice){const ok=await this.environment.playNotice(job.text);if(generation!==this.generation)return;this.message(ok?job.text:'Голос не загрузился. Игра продолжается.');this.next();return;}
        const engine=this.environment.engine();if(!engine){this.message(job.text);this.next();return;}
        const utterance=this.environment.utterance(job.text);this.current=utterance;
        utterance.lang='ru-RU';utterance.volume=1;
        utterance.rate=1;
        utterance.pitch=1;
        const voices=engine.getVoices().filter(voice=>/^ru(?:[-_]|$)/i.test(voice.lang));
        const voice=voices.find(voice=>/natural|svetlana|dariya/i.test(voice.name))??voices.find(voice=>voice.localService)??voices[0];if(voice)utterance.voice=voice;
        const finish=(failed=false)=>{
          if(generation!==this.generation||this.current!==utterance)return;
          if(this.watchdog)clearTimeout(this.watchdog);this.watchdog=null;
          utterance.onend=null;utterance.onerror=null;this.current=null;
          this.message(failed?'Браузер не воспроизвёл голос. Проверьте звук и доступность русского голоса.':job.text);
          this.next();
        };
        utterance.onend=()=>finish();utterance.onerror=()=>finish(true);
        this.watchdog=setTimeout(()=>{if(this.current!==utterance)return;try{engine.cancel();}catch{/* unavailable engine */}finish(true);},Math.min(60000,Math.max(15000,job.text.length*130)));
        engine.speak(utterance);
      }catch{
        if(this.watchdog)clearTimeout(this.watchdog);this.watchdog=null;this.current=null;this.message('Озвучка недоступна. Игра остаётся доступной без звука.');this.next();
      }
    };
    // A short host-like pause adds emphasis; correctness is already decided by the server.
    if(job.style==='result'&&job.pauseMs>0)this.timer=setTimeout(speak,job.pauseMs);else speak();
  }
}

export const announcer=new QuizAnnouncer({
  playNotice:playPartyVoice,stopNotice:stopPartyVoice,
  readQuestions:()=>typeof localStorage!=='undefined'&&localStorage.getItem('battle.readQuestions')==='on',
  engine:()=>typeof window!=='undefined'&&'speechSynthesis'in window?window.speechSynthesis:null,
  utterance:text=>new SpeechSynthesisUtterance(text),
  readEnabled:()=>typeof localStorage==='undefined'||localStorage.getItem('battle.announcements')!=='off',
  saveEnabled:enabled=>localStorage.setItem('battle.announcements',enabled?'on':'off'),
  playCue:cue=>soundtrack.playCue(cue),stopCue:()=>soundtrack.stopCue(),
  playbackChange:active=>soundtrack.setSpeechActive(active),enabledChange:enabled=>soundtrack.setEnabled(enabled),
});
soundtrack.setEnabled(announcer.getSnapshot().enabled);
