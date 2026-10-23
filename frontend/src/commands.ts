export type Action = {type:'select';index:number}|{type:'confirm'|'next'|'repeat'};
export const gestures:Record<string,Action>={Pointing_Up:{type:'select',index:0},Victory:{type:'select',index:1},Closed_Fist:{type:'select',index:2},Open_Palm:{type:'select',index:3},Thumb_Up:{type:'confirm'}};
export const confirmationThreshold=(selectionThreshold:number)=>Math.max(.6,selectionThreshold);
export const gestureHoldMs=(name:string)=>name==='Thumb_Up'?750:650;
export function voiceAction(text:string):Action|null {
  const t=text.toLocaleLowerCase('ru-RU').replaceAll('ё','е').replace(/[.,!?;:]/g,'').replace(/\s+/g,' ').trim();
  // Speech engines may format spoken ordinals as digits: «первый» -> «1».
  // Match the whole command so numbers inside unrelated/ambiguous text do nothing.
  const numeric=t.match(/^(?:(?:ответ|вариант)(?:\s+номер)?\s+|номер\s+)?([1-4])(?:[-\s]?(?:й|ый|ой|ий|я|е))?$/);
  if(numeric)return {type:'select',index:Number(numeric[1])-1};
  const groups=[['первый','первая','первое','один','ответ а','ответ a','вариант а','вариант a'],['второй','вторая','второе','два','ответ б','вариант б','ответ бэ'],['третий','третья','третье','три','ответ в','вариант в','ответ вэ'],['четвертый','четвертая','четвертое','четыре','ответ г','вариант г','ответ гэ']];
  const i=groups.findIndex(g=>g.includes(t));
  if(i>=0)return {type:'select',index:i};
  if(['подтвердить','подтверждаю','подтвердить ответ'].includes(t))return {type:'confirm'};
  if(['следующий','следующий вопрос','дальше'].includes(t))return {type:'next'};
  if(['повторить вопрос','повтори вопрос','повторить'].includes(t))return {type:'repeat'};
  return null;
}
export function canPerform(action:Action, state:{selected:number|null;answered:boolean;busy:boolean;hasQuestion:boolean}){
  if(state.busy||!state.hasQuestion)return false;
  if(action.type==='repeat')return true;
  if(action.type==='next')return state.answered;
  if(action.type==='confirm')return !state.answered&&state.selected!==null;
  return !state.answered;
}
export class GestureGate {
  private candidate='';private elapsed=0;private fired=false;private last=-Infinity;
  private lastSeen=-Infinity;private previousTime=0;
  constructor(private threshold=.65){}
  setThreshold(value:number){this.threshold=Math.max(.5,Math.min(.85,value));this.reset();}
  get progress(){return this.candidate?Math.min(1,this.elapsed/gestureHoldMs(this.candidate)):0;}
  reset(){this.candidate='';this.elapsed=0;this.fired=false;this.lastSeen=-Infinity;}
  update(name:string, confidence:number, time:number):Action|null {
    const valid=!!gestures[name]&&confidence>=(name==='Thumb_Up'?confirmationThreshold(this.threshold):this.threshold);
    if(!valid){
      // A brief missed classification must not restart the entire hold.
      // Missing/uncertain frames do not contribute to hold time.
      this.previousTime=time;
      if(time-this.lastSeen>250)this.reset();
      return null;
    }
    if(name!==this.candidate||time-this.lastSeen>350){
      this.candidate=name;this.elapsed=0;this.fired=false;
    }
    else this.elapsed+=Math.max(0,Math.min(time-this.previousTime,200));
    this.lastSeen=time;this.previousTime=time;
    const hold=gestureHoldMs(name);
    if(!this.fired&&this.elapsed>=hold&&time-this.last>=1200){this.last=time;this.fired=true;return gestures[name];}
    return null;
  }
}
