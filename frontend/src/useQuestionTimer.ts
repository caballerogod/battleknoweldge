import {useEffect,useRef,useState} from 'react';
import {remainingSeconds} from './countdown';
export function useQuestionTimer(deadline:number|null,enabled:boolean,onTimeout:()=>void,limit=30){
  const [seconds,setSeconds]=useState(limit),callback=useRef(onTimeout);callback.current=onTimeout;
  useEffect(()=>{
    if(deadline===null||!enabled)return;
    let lastAttempt=-Infinity;
    const tick=()=>{
      const now=performance.now(),left=remainingSeconds(deadline,now,limit);setSeconds(left);
      // Retry a failed/offline timeout save; the API prevents duplicate credit/answers.
      if(left===0&&now-lastAttempt>=1000){lastAttempt=now;callback.current();}
    };
    tick();const timer=setInterval(tick,100);return()=>clearInterval(timer);
  },[deadline,enabled,limit]);
  const current=deadline!==null&&enabled?remainingSeconds(deadline,performance.now(),limit):seconds;
  return {seconds:current,expired:enabled&&current===0};
}
