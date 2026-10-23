import {useEffect,useRef,useState} from 'react';
import {remainingSeconds} from './countdown';
export function useQuestionTimer(deadline:number|null,enabled:boolean,onTimeout:()=>void){
  const [seconds,setSeconds]=useState(30),callback=useRef(onTimeout);callback.current=onTimeout;
  useEffect(()=>{
    if(deadline===null||!enabled)return;
    let lastAttempt=-Infinity;
    const tick=()=>{
      const now=performance.now(),left=remainingSeconds(deadline,now);setSeconds(left);
      // Retry a failed/offline timeout save; the API prevents duplicate credit/answers.
      if(left===0&&now-lastAttempt>=1000){lastAttempt=now;callback.current();}
    };
    tick();const timer=setInterval(tick,100);return()=>clearInterval(timer);
  },[deadline,enabled]);
  const current=deadline!==null&&enabled?remainingSeconds(deadline,performance.now()):seconds;
  return {seconds:current,expired:enabled&&current===0};
}
