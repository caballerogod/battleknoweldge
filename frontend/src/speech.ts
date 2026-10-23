import {voiceAction,type Action} from './commands';

export type SpeechEvent={resultIndex:number;results:{length:number;[index:number]:{isFinal:boolean;[index:number]:{transcript:string}}}};
export type SpeechEngine={
  lang:string;continuous:boolean;interimResults:boolean;
  onresult:((event:SpeechEvent)=>void)|null;onerror:((event:{error:string})=>void)|null;
  onend:(()=>void)|null;onstart:(()=>void)|null;onnomatch:(()=>void)|null;
  start:()=>void;abort:()=>void;
};
export type SpeechState='off'|'starting'|'listening'|'paused';
type Handlers={state:(state:SpeechState)=>void;text:(text:string)=>void;error:(text:string)=>void;action:(action:Action)=>void;isSpeaking:()=>boolean;ready?:()=>void;phrase?:(text:string)=>void};
const browserHint='Откройте игру в обычном Chrome или Edge: http://127.0.0.1:5173. Во встроенном браузере речевой сервис может быть недоступен.';
export function speechError(code:string){
  const errors:Record<string,string>={
    'not-allowed':'Доступ к микрофону запрещён браузером или Windows. Разрешите микрофон в настройках сайта и Windows → Конфиденциальность → Микрофон.',
    'service-not-allowed':'Браузер не разрешает речевой сервис. '+browserHint,
    'audio-capture':'Микрофон не найден или занят. Проверьте подключение и устройство ввода в настройках браузера.',
    network:'Не удалось подключиться к речевому сервису браузера. Если шкала проверки реагирует, звук поступает; проверьте интернет и откройте игру в обычном Chrome или Edge.',
    'language-not-supported':'Русский язык недоступен в речевом сервисе этого браузера. '+browserHint,
    unsupported:'Распознавание речи не поддерживается. '+browserHint,
    timeout:'Речевой сервис не запустился за 8 секунд. '+browserHint,
    silent:'Речь не распознана в трёх попытках. Нажмите «Проверить микрофон» и убедитесь, что выбран правильный микрофон.',
  };
  return errors[code]??`Ошибка распознавания: ${code}. ${browserHint}`;
}

/** One utterance per engine session, guarded restart and explicit startup failure. */
export class SpeechController{
  private engine:SpeechEngine|null=null;
  private wanted=false;
  private epoch=0;
  private startup:ReturnType<typeof setTimeout>|null=null;
  private restart:ReturnType<typeof setTimeout>|null=null;
  private emptySessions=0;
  private lastTranscript='';
  private playbackActive=false;
  private readyNotified=false;
  constructor(private create:()=>SpeechEngine|null,private handlers:Handlers){}
  setPlaybackActive(active:boolean){
    if(active===this.playbackActive)return;
    this.playbackActive=active;if(!this.wanted)return;
    if(active){this.stop(false);this.wanted=true;this.handlers.state('paused');this.handlers.text('Игра говорит. Прослушивание продолжится после озвучки.');}
    else this.begin(this.epoch);
  }
  stop(notify=true){
    this.wanted=false;this.epoch++;
    if(this.startup)clearTimeout(this.startup);
    if(this.restart)clearTimeout(this.restart);
    this.startup=null;this.restart=null;
    const engine=this.engine;this.engine=null;
    if(engine){engine.onstart=null;engine.onend=null;engine.onerror=null;engine.onresult=null;engine.onnomatch=null;try{engine.abort();}catch{/* already stopped */}}
    if(notify){this.handlers.state('off');this.handlers.text('Микрофон выключен');}
  }
  start(){
    this.stop(false);this.wanted=true;this.emptySessions=0;this.lastTranscript='';this.readyNotified=false;this.handlers.error('');
    this.begin(this.epoch);
  }
  private fail(code:string){this.stop(false);this.handlers.state('off');this.handlers.error(speechError(code));this.handlers.text('Голосовое управление остановлено');}
  private begin(epoch:number){
    if(!this.wanted||epoch!==this.epoch)return;
    if(this.playbackActive){this.handlers.state('paused');this.handlers.text('Игра говорит. Прослушивание продолжится после озвучки.');return;}
    let r:SpeechEngine|null;
    try{r=this.create();}catch{this.fail('unsupported');return;}
    if(!r){this.fail('unsupported');return;}
    this.engine=r;
    const active=()=>this.wanted&&epoch===this.epoch&&this.engine===r;
    let gotResult=false;
    r.lang='ru-RU';r.continuous=false;r.interimResults=true;
    this.handlers.state('starting');this.handlers.text(this.lastTranscript||'Подключаю речевой сервис…');
    this.startup=setTimeout(()=>{if(active())this.fail('timeout');},8000);
    r.onstart=()=>{if(!active())return;if(this.startup)clearTimeout(this.startup);this.startup=null;this.handlers.state('listening');this.handlers.text(this.lastTranscript||'Слушаю. Скажите одну команду и сделайте паузу.');if(!this.readyNotified){this.readyNotified=true;this.handlers.ready?.();}};
    r.onresult=e=>{
      if(!active()||this.handlers.isSpeaking())return;
      for(let i=e.resultIndex;i<e.results.length;i++){
        const result=e.results[i],phrase=result[0]?.transcript??'';
        if(!result.isFinal){this.handlers.text(`Слышу: «${phrase}»…`);continue;}
        gotResult=true;this.emptySessions=0;
        if(this.handlers.phrase){this.lastTranscript=`«${phrase}»`;this.handlers.text(this.lastTranscript);this.handlers.phrase(phrase);continue;}
        const action=voiceAction(phrase);
        this.lastTranscript=`«${phrase}»${action?'':' — команда не распознана'}`;this.handlers.text(this.lastTranscript);
        if(action)this.handlers.action(action);
      }
    };
    r.onnomatch=()=>{if(active())this.handlers.text('Не удалось разобрать команду. Скажите, например, «первый».');};
    r.onerror=e=>{
      if(!active())return;
      if(e.error==='no-speech'){this.handlers.text('Пока не слышу речь. Скажите команду ближе к микрофону.');return;}
      this.fail(e.error);
    };
    r.onend=()=>{
      if(!active())return;
      if(this.startup)clearTimeout(this.startup);this.startup=null;
      r.onresult=null;r.onerror=null;r.onend=null;r.onstart=null;r.onnomatch=null;this.engine=null;
      if(!gotResult&&!this.handlers.isSpeaking())this.emptySessions++;
      if(this.emptySessions>=3){this.fail('silent');return;}
      this.handlers.state('starting');
      this.restart=setTimeout(()=>{this.restart=null;this.begin(epoch);},350);
    };
    try{r.start();}catch(e){this.fail(e instanceof DOMException&&e.name==='NotAllowedError'?'not-allowed':'service-not-allowed');}
  }
}
