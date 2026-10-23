/** Recognition ignores playback and a short echo tail; no microphone settings are changed. */
let active=0,tailUntil=0;
export function beginQuestionMedia(){active++;let released=false;return()=>{if(released)return;released=true;active=Math.max(0,active-1);tailUntil=Date.now()+350;};}
export function isQuestionMediaPlaying(){return active>0||Date.now()<tailUntil;}
