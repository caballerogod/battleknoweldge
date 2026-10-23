const phrases:Record<string,string>={'Камера включена.':'camera-on','Микрофон включён.':'microphone-on','Ответ верный!':'correct','Ответ неверный.':'incorrect','Время вышло.':'timeout','Битва начинается!':'round-start'};
let stopCurrent:(()=>void)|undefined;
export function stopPartyVoice(){stopCurrent?.();}
/** Bundled neural recordings play offline; cancellation also releases the recognition guard. */
export function playPartyVoice(text:string):Promise<boolean>{
 stopPartyVoice();const key=phrases[text];if(!key||typeof Audio==='undefined')return Promise.resolve(false);
 return new Promise(resolve=>{
  const audio=new Audio(`/audio/voice/${key}.mp3?v=party-1`);audio.volume=.85;
  let finished=false;const finish=(ok:boolean)=>{if(finished)return;finished=true;clearTimeout(timer);audio.onended=null;audio.onerror=null;audio.pause();if(stopCurrent===cancel)stopCurrent=undefined;resolve(ok);};
  const cancel=()=>finish(false),timer=setTimeout(cancel,10000);stopCurrent=cancel;
  audio.onended=()=>finish(true);audio.onerror=cancel;void audio.play().catch(cancel);
 });
}
