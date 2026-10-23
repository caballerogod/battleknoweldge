import {isQuestionMediaPlaying} from './questionMediaPlayback';
import {memo,useEffect,useRef,useState,useSyncExternalStore} from 'react';
import {Aperture,Camera,CameraOff,ChevronDown,Mic,MicOff,Settings2,Volume2,VolumeX} from 'lucide-react';
import type {GestureRecognizer} from '@mediapipe/tasks-vision';
import {GestureGate,confirmationThreshold,gestureHoldMs,type Action} from './commands';
import {SpeechController,type SpeechEngine,type SpeechState} from './speech';
import {useMicrophoneCheck} from './useMicrophoneCheck';
import {announcer} from './announcer';
import {soundtrack} from './soundtrack';
import {fingerCount,FingerHold} from './triviaCommands';

type SpeechWindow=Window & {SpeechRecognition?:new()=>SpeechEngine;webkitSpeechRecognition?:new()=>SpeechEngine};
const instructions=[['☝','A','Pointing_Up'],['✌','B','Victory'],['✊','C','Closed_Fist'],['✋','D','Open_Palm'],['👍','✓','Thumb_Up']];
const names:Record<string,string>={Pointing_Up:'Указательный палец',Victory:'Два пальца',Closed_Fist:'Кулак',Open_Palm:'Ладонь',Thumb_Up:'Большой палец вверх'};
const bones=[[0,1,2,3,4],[0,5,6,7,8],[5,9,10,11,12],[9,13,14,15,16],[13,17,18,19,20],[0,17]];

export const RecognitionPanel=memo(function RecognitionPanel({onAction,onPhrase,board=false,boardPaging=false}:{onAction:(action:Action)=>boolean;onPhrase?:(text:string)=>void;board?:boolean;boardPaging?:boolean}){
  const video=useRef<HTMLVideoElement>(null),canvas=useRef<HTMLCanvasElement>(null);
  const callback=useRef(onAction);callback.current=onAction;
  const phraseCallback=useRef(onPhrase);phraseCallback.current=onPhrase;
  const stream=useRef<MediaStream|null>(null),model=useRef<GestureRecognizer|null>(null),frame=useRef(0),version=useRef(0);
  const controller=useRef<SpeechController|null>(null),gate=useRef<GestureGate|null>(null);
  const [camera,setCamera]=useState(false),[loading,setLoading]=useState(false),[micState,setMicState]=useState<SpeechState>('off');
  const [gesture,setGesture]=useState('Камера выключена'),[speech,setSpeech]=useState('Микрофон выключен');
  const [cameraError,setCameraError]=useState(''),[micError,setMicError]=useState('');
  const [progress,setProgress]=useState(0),[sensitivity,setSensitivity]=useState(.65),[actionStatus,setActionStatus]=useState('');
  const sensitivityRef=useRef(sensitivity);sensitivityRef.current=sensitivity;
  const micCheck=useMicrophoneCheck();
  const [readQuestions,setReadQuestions]=useState(()=>localStorage.getItem('battle.readQuestions')==='on');
  const audio=useSyncExternalStore(announcer.subscribe,announcer.getSnapshot);
  function stopCamera(){version.current++;cancelAnimationFrame(frame.current);stream.current?.getTracks().forEach(t=>t.stop());stream.current=null;model.current?.close();model.current=null;if(video.current)video.current.srcObject=null;setCamera(false);setLoading(false);setProgress(0);setGesture('Камера выключена');canvas.current?.getContext('2d')?.clearRect(0,0,canvas.current.width,canvas.current.height);}
  function stopMic(){controller.current?.stop();}
  useEffect(()=>()=>{version.current++;cancelAnimationFrame(frame.current);stream.current?.getTracks().forEach(t=>t.stop());model.current?.close();controller.current?.stop(false);},[]);
  useEffect(()=>announcer.onPlaybackChange(active=>controller.current?.setPlaybackActive(active)),[]);
  useEffect(()=>{soundtrack.setMicrophoneActive(micCheck.checking||micState!=='off');},[micCheck.checking,micState]);
  useEffect(()=>()=>soundtrack.setMicrophoneActive(false),[]);
  async function startCamera(){
    const id=++version.current;setLoading(true);setCameraError('');setActionStatus('');
    try{
      if(!navigator.mediaDevices?.getUserMedia)throw new Error('Камера доступна на localhost или через HTTPS.');
      const media=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480},facingMode:'user'},audio:false});
      if(id!==version.current){media.getTracks().forEach(t=>t.stop());return;}
      stream.current=media;if(!video.current)throw new Error('Не удалось открыть окно камеры');
      video.current.srcObject=media;await video.current.play();
      const {FilesetResolver,GestureRecognizer}=await import('@mediapipe/tasks-vision');
      const fileset=await FilesetResolver.forVisionTasks('/wasm');
      const recognizer=await GestureRecognizer.createFromOptions(fileset,{baseOptions:{modelAssetPath:'/models/gesture_recognizer.task'},runningMode:'VIDEO',numHands:1,minHandDetectionConfidence:.5,minHandPresenceConfidence:.5,minTrackingConfidence:.5});
      if(id!==version.current){recognizer.close();return;}
      model.current=recognizer;setCamera(true);setLoading(false);
      const filter=new GestureGate(sensitivityRef.current),fingers=new FingerHold();gate.current=filter;let last=0,lastVideo=-1;
      const tick=(time:number)=>{
        if(id!==version.current)return;
        try{
          const v=video.current;
          if(v&&v.readyState>=2&&time-last>=65&&v.currentTime!==lastVideo){
            last=time;lastVideo=v.currentTime;
            const result=recognizer.recognizeForVideo(v,time),g=result.gestures[0]?.[0],hand=result.landmarks[0];
            const overlay=canvas.current,ctx=overlay?.getContext('2d');
            if(overlay&&ctx){
              if(overlay.width!==v.videoWidth||overlay.height!==v.videoHeight){overlay.width=v.videoWidth;overlay.height=v.videoHeight;}
              ctx.clearRect(0,0,overlay.width,overlay.height);
              if(hand){ctx.strokeStyle='#8de8c3';ctx.fillStyle='#d8c1ff';ctx.lineWidth=3;
                for(const chain of bones){ctx.beginPath();chain.forEach((index,i)=>{const p=hand[index];if(i===0)ctx.moveTo(p.x*overlay.width,p.y*overlay.height);else ctx.lineTo(p.x*overlay.width,p.y*overlay.height);});ctx.stroke();}
                for(const p of hand){ctx.beginPath();ctx.arc(p.x*overlay.width,p.y*overlay.height,4,0,Math.PI*2);ctx.fill();}
              }
            }
            setGesture(g&&names[g.categoryName]?`${names[g.categoryName]} · ${Math.round(g.score*100)}%`:hand?'Рука найдена — покажите один из пяти жестов':'Рука не найдена — поместите всю кисть в кадр');
            let action:Action|null=null;
            if(board){
              const thumb=g?.categoryName==='Thumb_Up'&&g.score>=confirmationThreshold(sensitivityRef.current);
              const fist=boardPaging&&g?.categoryName==='Closed_Fist'&&g.score>=sensitivityRef.current;
              const count=thumb||fist?null:fingerCount(hand);
              const chosen=fingers.update(count,time);
              action=filter.update(thumb?'Thumb_Up':fist?'Closed_Fist':'',thumb||fist?g!.score:0,time);
              if(fist&&action)action={type:'next'};
              if(chosen!==null)action={type:'select',index:chosen-1};
              setGesture(thumb?'👍 Подтвердить':fist?'✊ Другая группа тем':count?`Пальцев: ${count}. Удерживайте 0,8 с.`:hand?'Покажите 1–5 пальцев или 👍':'Рука не найдена — поместите всю кисть в кадр');
              setProgress(thumb||fist?filter.progress:fingers.progress);
            }else{action=filter.update(g?.categoryName??'',g?.score??0,time);setProgress(filter.progress);}
            if(action){const accepted=callback.current(action);setActionStatus(accepted?(action.type==='select'?(board?`Выбрана позиция ${action.index+1}`:`Выбран ответ ${'ABCD'[action.index]}`):action.type==='next'?'Группа тем переключена':'Подтверждение отправлено'):'Сейчас действие недоступно: проверьте текущий шаг и выбор.');}
          }
          frame.current=requestAnimationFrame(tick);
        }catch(e){stopCamera();setCameraError('Ошибка анализа видео: '+String(e));}
      };
      frame.current=requestAnimationFrame(tick);
      media.getVideoTracks()[0].onended=()=>{if(id===version.current){stopCamera();setCameraError('Камера отключена устройством. Подключите её и повторите.');}};
      announcer.announce('camera-on');
    }catch(e){
      if(id!==version.current)return;
      stopCamera();const name=(e as DOMException).name;
      setCameraError(name==='NotAllowedError'?'Доступ к камере запрещён. Разрешите его в настройках сайта.':name==='NotFoundError'?'Камера не найдена. Подключите веб-камеру.':name==='NotReadableError'?'Камера занята другим приложением.':name==='NotSupportedError'?'Захват видео недоступен в этой среде. Откройте игру в обычном Chrome или Edge на компьютере с камерой.':`Не удалось загрузить камеру или модель. ${String(e)}`);
    }
  }
  function startMic(){
    micCheck.stop();
    if(!controller.current)controller.current=new SpeechController(()=>{const w=window as SpeechWindow,Ctor=w.SpeechRecognition??w.webkitSpeechRecognition;return Ctor?new Ctor():null;},
      {state:setMicState,text:setSpeech,error:setMicError,action:a=>{if(!callback.current(a))setSpeech('Команда распознана, но сейчас недоступна. Сначала выберите ответ или дождитесь его проверки.');},isSpeaking:()=>isQuestionMediaPlaying()||announcer.isBlocking||!!window.speechSynthesis?.speaking,ready:()=>announcer.announce('microphone-on'),...(onPhrase?{phrase:(text:string)=>phraseCallback.current?.(text)}:{})});
    controller.current.setPlaybackActive(announcer.isBlocking);
    controller.current.start();
  }
  async function copyAddress(){try{await navigator.clipboard.writeText(window.location.origin);setSpeech('Адрес скопирован. Вставьте его в адресную строку обычного Chrome или Edge.');}catch{setSpeech('Откройте в Chrome или Edge: '+window.location.origin);}}
  return <aside className="panel controls" aria-label="Камера и голос"><h3>Ваше управление</h3>
    <div className={'camera-view '+(camera?'live':'')}><video ref={video} autoPlay muted playsInline aria-label="Видео с веб-камеры"/><canvas ref={canvas} className="hand-overlay" aria-hidden="true"/>{!camera&&<div className="camera-placeholder"><Aperture size={35}/><span>{loading?'Подготовка камеры…':'Камера выключена'}</span></div>}{camera&&<div className="show-camera-progress" role="progressbar" aria-label="Подтверждение жеста" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress*100)} style={{width:`${progress*100}%`}}/>}</div>
    <button className="secondary full camera-toggle" onClick={()=>camera||loading?stopCamera():void startCamera()}>{camera||loading?<CameraOff size={17}/>:<Camera size={17}/>} {camera||loading?'Выключить камеру':'Включить камеру'}</button>
    {camera&&<p className="device-state" role="status">{gesture}</p>}{cameraError&&<p className="device-error" role="alert">{cameraError}</p>}
    {actionStatus&&<p className="device-state" role="status">{actionStatus}</p>}
    <button className={'secondary full mic-toggle '+(micState==='listening'?'listening':'')} onClick={()=>micState!=='off'?stopMic():startMic()}>{micState!=='off'?<MicOff size={18}/>:<Mic size={18}/>} {micState==='off'?'Включить микрофон':micState==='starting'?'Отменить запуск':'Выключить микрофон'}</button>
    {micState!=='off'&&<p className="device-state" role="status">{speech}</p>}{micError&&<p className="device-error" role="alert">{micError}</p>}
    <p className="show-voice-hint">{board?'Назовите тему и стоимость. В вариантах скажите «первый»…«четвёртый», затем «подтвердить». На открытый вопрос произнесите сам ответ.':'«Второй» → выбор B · «Подтвердить»'}</p>
    <details className="show-settings"><summary><Settings2 size={18}/>Настройки управления<ChevronDown size={16}/></summary>
      <div className="hold-meter"><span>Удержание жеста</span><div className="bar" role="progressbar" aria-label="Удержание жеста" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress*100)}><i style={{width:`${progress*100}%`}}/></div></div>
      <label className="sensitivity">Чувствительность<select value={sensitivity} onChange={e=>{const value=Number(e.target.value);setSensitivity(value);gate.current?.setThreshold(value);setProgress(0);}}><option value={.65}>Обычная · 65%</option><option value={.55}>Повышенная · 55%</option><option value={.75}>Строгая · 75%</option></select></label>
      {!board&&<div className="gesture-legend">{instructions.map(([emoji,key,name])=><div key={name} title={name}><span>{emoji}</span><b>{key}</b></div>)}</div>}
      <p className="caption">{board?'1–5 пальцев: сначала тема, затем стоимость (100–500). Удерживайте 0,8 с. Между одинаковыми числами уберите руку на 0,3 с. 👍 подтверждает клетку или сказанный ответ.':`A–D: удерживайте 0,65 с. 👍 удерживайте ${gestureHoldMs('Thumb_Up')/1000} с при уверенности от ${Math.round(confirmationThreshold(sensitivity)*100)}%.`} Вся кисть должна быть видна в кадре.</p>
      <button className="secondary full" onClick={()=>{if(micCheck.checking)micCheck.stop();else{stopMic();void micCheck.start();}}}>{micCheck.checking?'Остановить проверку':'Проверить микрофон · 7 с'}</button>
      {micCheck.checking&&<div className="mic-meter"><span>Уровень звука: {micCheck.level}%</span><div className="bar" role="meter" aria-label="Уровень микрофона" aria-valuemin={0} aria-valuemax={100} aria-valuenow={micCheck.level}><i style={{width:`${micCheck.level}%`}}/></div></div>}
      {micCheck.message&&<p className="device-state" role="status">{micCheck.message}</p>}
      <p className="caption">{board?'«Третья тема за двести», название темы, «подтвердить», «исправить ответ», «пропустить», «повторить вопрос», «дальше». Ответьте одной фразой и подтвердите отдельной командой.':'«Первый»…«четвёртый», «1»…«4», «ответ А/Б/В/Г», «подтвердить», «следующий», «повторить вопрос». Говорите одну команду и делайте паузу.'}</p>
      <p className="browser-help">Для голоса используйте Chrome или Edge. Во встроенном браузере речевой сервис может быть недоступен.</p><button className="text-button" onClick={()=>void copyAddress()}>Скопировать адрес для браузера</button>
      <p className="caption">Во время работы микрофона фон приостанавливается. <a href="/audio-preview.html" target="_blank" rel="noreferrer">Прослушать сигналы</a></p>
      <p className="privacy">Видео и проверка уровня звука обрабатываются локально. Распознавание речи может использовать сетевой сервис браузера.</p>
    </details>
    <label><input type="checkbox" checked={readQuestions} onChange={e=>{setReadQuestions(e.target.checked);localStorage.setItem('battle.readQuestions',e.target.checked?'on':'off');announcer.cancel();}}/> Читать вопросы вслух</label><button className="show-audio-toggle" aria-label={'Звук игры: '+(audio.enabled?'включён':'выключен')} aria-pressed={audio.enabled} onClick={()=>announcer.setEnabled(!audio.enabled)}>{audio.enabled?<Volume2 size={20}/>:<VolumeX size={20}/>} Звук {audio.enabled?'включён':'выключен'}<span className="show-switch" aria-hidden="true"><i/></span></button><p className="sr-only" role="status">{audio.message}</p>
  </aside>;
});
