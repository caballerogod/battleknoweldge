import {useEffect,useRef,useState} from 'react';

/** Local signal check: never records, uploads, or interprets speech. */
export function useMicrophoneCheck(){
  const [checking,setChecking]=useState(false),[level,setLevel]=useState(0),[message,setMessage]=useState('');
  const current=useRef({epoch:0,stream:null as MediaStream|null,context:null as AudioContext|null,frame:0,timer:0});
  function release(){const r=current.current;r.epoch++;cancelAnimationFrame(r.frame);clearTimeout(r.timer);r.stream?.getTracks().forEach(t=>t.stop());r.stream=null;void r.context?.close().catch(()=>{});r.context=null;}
  function stop(){release();setChecking(false);setLevel(0);if(checking)setMessage('Проверка остановлена. Микрофон освобождён.');}
  useEffect(()=>()=>release(),[]);
  async function start(){
    release();const epoch=current.current.epoch;setChecking(true);setLevel(0);setMessage('Разрешите доступ и скажите несколько слов…');
    try{
      if(!navigator.mediaDevices?.getUserMedia)throw new Error('Проверка доступна на localhost в обычном Chrome или Edge.');
      const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
      if(epoch!==current.current.epoch){stream.getTracks().forEach(t=>t.stop());return;}
      current.current.stream=stream;
      const context=new AudioContext();current.current.context=context;await context.resume();
      if(epoch!==current.current.epoch)return;
      const analyser=context.createAnalyser();analyser.fftSize=1024;context.createMediaStreamSource(stream).connect(analyser);
      const samples=new Float32Array(analyser.fftSize);let peak=0,last=0;
      const label=stream.getAudioTracks()[0]?.label||'Микрофон по умолчанию';setMessage(label+' — говорите, наблюдая за шкалой.');
      const tick=(time:number)=>{
        if(epoch!==current.current.epoch)return;
        if(time-last>=100){last=time;analyser.getFloatTimeDomainData(samples);const rms=Math.sqrt(samples.reduce((sum,n)=>sum+n*n,0)/samples.length);const value=Math.min(100,Math.round(rms*500));peak=Math.max(peak,value);setLevel(value);}
        current.current.frame=requestAnimationFrame(tick);
      };
      current.current.frame=requestAnimationFrame(tick);
      current.current.timer=window.setTimeout(()=>{if(epoch!==current.current.epoch)return;stop();setMessage(peak>=8?`${label}: звук поступает (пик ${peak}%). Если команды не распознаются, проблема может быть в речевом сервисе браузера.`:`${label}: очень тихий сигнал (пик ${peak}%). Проверьте выбранный микрофон, громкость ввода и кнопку отключения звука в Windows.`);},7000);
    }catch(e){if(epoch!==current.current.epoch)return;stop();setMessage((e as DOMException).name==='NotAllowedError'?'Доступ к микрофону запрещён. Разрешите его в браузере и настройках конфиденциальности Windows.':`Не удалось получить звук с микрофона: ${e instanceof Error?e.message:String(e)}`);}
  }
  return {checking,level,message,start,stop};
}
