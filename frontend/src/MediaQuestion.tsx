import {forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import {announcer} from './announcer';
import {soundtrack} from './soundtrack';
import {beginQuestionMedia} from './questionMediaPlayback';
export type QuestionMedia={kind:'image'|'audio'|'video';url:string;mask:'none'|'blur'|'pixel';level:number;hint?:string;credit?:string;source?:string};
export type MediaController={play:()=>void;stop:()=>void};
export const MediaQuestion=forwardRef<MediaController,{media:QuestionMedia;disabled?:boolean;timeLimit?:number}>(function MediaQuestion({media,disabled=false,timeLimit=60},ref){
 const canvas=useRef<HTMLCanvasElement>(null),element=useRef<HTMLMediaElement|null>(null),release=useRef<(()=>void)|null>(null);
 const [failed,setFailed]=useState(false),[playing,setPlaying]=useState(false),[position,setPosition]=useState(0),[duration,setDuration]=useState(0);
 function ended(){release.current?.();release.current=null;setPlaying(false);soundtrack.setMediaActive(false);}
 function stop(){element.current?.pause();ended();}
 function play(){if(disabled||failed)return;announcer.cancel();const node=element.current;if(node){if(node.ended)node.currentTime=0;void node.play().catch(()=>{ended();setFailed(true);});}}
 useImperativeHandle(ref,()=>({play,stop}));
 useEffect(()=>{setFailed(false);setPosition(0);setDuration(0);const node=element.current;return()=>{node?.pause();release.current?.();release.current=null;soundtrack.setMediaActive(false);};},[media.url]);
 useEffect(()=>{if(disabled)stop();},[disabled]);
 useEffect(()=>{
  if(media.kind!=='image'||media.mask==='none')return;
  let cancelled=false;const img=new Image();img.onload=()=>{if(cancelled)return;const node=canvas.current,ctx=node?.getContext('2d');if(!node||!ctx)return;
   const level=Math.max(1,Math.min(5,media.level)),fraction=1-level*.008;
   const sw=img.naturalWidth*fraction,sh=Math.min(img.naturalHeight*fraction,sw*9/16),sx=(img.naturalWidth-sw)/2,sy=(img.naturalHeight-sh)/2;
   node.width=media.mask==='pixel'?[180,150,125,105,90][level-1]:640;node.height=Math.round(node.width*9/16);
   ctx.drawImage(img,sx,sy,sw,sh,0,0,node.width,node.height);
  };img.onerror=()=>{if(!cancelled)setFailed(true);};img.src=media.url;return()=>{cancelled=true;img.onload=null;img.onerror=null;};
 },[media.url,media.mask,media.level,media.kind]);
 const credit=media.credit&&<figcaption>{media.credit}{media.source&&<> · <a href={media.source} target="_blank" rel="noreferrer">Источник</a></>}</figcaption>;
 return <figure className={'quiz-media quiz-media-'+media.kind}>
  {failed?<p role="alert">Не удалось загрузить фрагмент. Можно пропустить вопрос без штрафа.</p>:media.kind==='image'?media.mask==='none'?<img src={media.url} alt="Иллюстрация к вопросу" onError={()=>setFailed(true)}/>:<><div className="quiz-frame-window"><canvas ref={canvas} role="img" aria-label="Скрытый фрагмент сериала" className={media.mask} style={media.mask==='blur'?{filter:`blur(${.5+media.level*.35}px)`}:undefined}/></div><p>Назовите сериал · {media.mask==='pixel'?'пиксели':'размытый фрагмент'}</p></>:<>
   {media.kind==='video'?<video ref={n=>{element.current=n;}} src={media.url} preload="metadata" playsInline muted onPlay={()=>{release.current?.();release.current=beginQuestionMedia();setPlaying(true);soundtrack.setMediaActive(true);}} onPause={ended} onEnded={ended} onError={()=>{ended();setFailed(true);}} onLoadedMetadata={()=>setDuration(element.current?.duration??0)} onTimeUpdate={()=>setPosition(element.current?.currentTime??0)}/>:<audio ref={n=>{element.current=n;}} src={media.url} preload="metadata" onPlay={()=>{release.current?.();release.current=beginQuestionMedia();setPlaying(true);soundtrack.setMediaActive(true);}} onPause={ended} onEnded={ended} onError={()=>{ended();setFailed(true);}} onLoadedMetadata={()=>setDuration(element.current?.duration??0)} onTimeUpdate={()=>setPosition(element.current?.currentTime??0)}/>}
   <div className="quiz-media-controls"><button type="button" disabled={disabled} onClick={()=>playing?stop():play()}>{playing?'Пауза':media.kind==='audio'?'Прослушать фрагмент':'Посмотреть фрагмент'}</button><span>{Math.floor(position)} / {Math.ceil(duration)||'…'} сек.</span></div><progress aria-label="Воспроизведение фрагмента" value={position} max={duration||1}/><p>Можно сказать «воспроизвести». Таймер вопроса — {timeLimit} секунд, включая фрагмент.</p>
  </>}{media.hint&&<p className="quiz-media-hint"><strong>Подсказка:</strong> {media.hint}</p>}{credit}
 </figure>;
});
