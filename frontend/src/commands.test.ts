import {describe,it,expect} from 'vitest';
import {voiceAction,GestureGate,canPerform,gestures} from './commands';
describe('Russian commands',()=>{
  it.each([['ПЕРВЫЙ!',0],['Ответ Б',1],['ответ в',2],['Четвёртый',3],['ответ Г.',3],['ответ a',0]])('%s', (s,i)=>expect(voiceAction(s)).toEqual({type:'select',index:i}));
  it.each([['1',0],['2',1],['3',2],['4',3],['1.',0],['1-й',0],['2-й',1],['3-й',2],['4-й',3],['ответ 1',0],['вариант 2',1],['номер 3',2],['ответ номер 4',3]])('recognizer numeric transcript %s selects answer', (s,i)=>expect(voiceAction(s)).toEqual({type:'select',index:i}));
  it.each(['0','5','11','не 1','1 или 2','ответ 1 или 2','21','1 2','1.5'])('rejects ambiguous numeric phrase %s',s=>expect(voiceAction(s)).toBeNull());
  it('rejects ambiguity and unrelated words',()=>{for(const s of ['не первый','первый или второй','абракадабра',''])expect(voiceAction(s)).toBeNull();});
  it('maps navigation',()=>{expect(voiceAction('Подтвердить')).toEqual({type:'confirm'});expect(voiceAction('Следующий')).toEqual({type:'next'});expect(voiceAction('Повторить вопрос')).toEqual({type:'repeat'});});
});
describe('gesture stability',()=>{
  function frames(g:GestureGate,name:string,score:number,start:number,end:number){const actions=[];for(let t=start;t<=end;t+=100){const a=g.update(name,score,t);if(a)actions.push(a);}return actions;}
  it('requires sustained evidence and fires only once',()=>{const g=new GestureGate();expect(frames(g,'Victory',.9,0,600)).toEqual([]);expect(g.progress).toBeCloseTo(600/650);expect(g.update('Victory',.9,700)).toEqual({type:'select',index:1});expect(frames(g,'Victory',.9,800,3000)).toEqual([]);});
  it('tolerates one missed classification without counting it as evidence',()=>{const g=new GestureGate();frames(g,'Victory',.8,0,300);g.update('None',.1,400);expect(g.progress).toBeCloseTo(300/650);expect(frames(g,'Victory',.8,500,900)).toEqual([{type:'select',index:1}]);});
  it('long loss resets progress',()=>{const g=new GestureGate();frames(g,'Victory',.8,0,300);g.update('',0,600);expect(g.progress).toBe(0);expect(frames(g,'Victory',.8,700,1200)).toEqual([]);});
  it('does not count sparse frames across a stall',()=>{const g=new GestureGate();g.update('Victory',.9,0);expect(g.update('Victory',.9,3000)).toBeNull();expect(g.progress).toBe(0);});
  it('confirms with realistic 70% Thumb_Up confidence after a selection',()=>{const g=new GestureGate();expect(frames(g,'Victory',.7,0,700)).toEqual([{type:'select',index:1}]);expect(frames(g,'Thumb_Up',.7,800,2000)).toEqual([{type:'confirm'}]);expect(frames(g,'Thumb_Up',.7,2100,4000)).toEqual([]);});
  it('accumulates intermittent confident thumb frames without accepting low confidence',()=>{const g=new GestureGate();const actions=[];for(let t=0;t<=2400;t+=100){const a=g.update('Thumb_Up',t%200===0?.72:.4,t);if(a)actions.push(a);}expect(actions).toEqual([{type:'confirm'}]);});
  it('supports sensitivity but rejects confirmation below its minimum',()=>{const g=new GestureGate(.55);expect(frames(g,'Thumb_Up',.59,0,1600)).toEqual([]);expect(frames(g,'Thumb_Up',.62,1700,2500)).toEqual([{type:'confirm'}]);});
  it('observes cooldown after a different gesture',()=>{const g=new GestureGate();frames(g,'Victory',.9,0,700);expect(frames(g,'Thumb_Up',.9,800,1800)).toEqual([]);expect(g.update('Thumb_Up',.9,1900)).toEqual({type:'confirm'});});
  it('brief low confidence after firing does not issue a duplicate',()=>{const g=new GestureGate();frames(g,'Victory',.9,0,2000);g.update('Victory',.2,2100);expect(frames(g,'Victory',.9,2200,4000)).toEqual([]);});
  it('maps only five supported gestures',()=>expect(Object.keys(gestures)).toHaveLength(5));
});
describe('game action guards',()=>{
  const s={selected:null,answered:false,busy:false,hasQuestion:true};
  it('cannot confirm empty selection',()=>expect(canPerform({type:'confirm'},s)).toBe(false));
  it('cannot skip unanswered question',()=>expect(canPerform({type:'next'},s)).toBe(false));
  it('allows confirm only once',()=>{expect(canPerform({type:'confirm'},{...s,selected:0})).toBe(true);expect(canPerform({type:'confirm'},{...s,selected:0,answered:true})).toBe(false);});
  it('blocks busy actions',()=>expect(canPerform({type:'select',index:0},{...s,busy:true})).toBe(false));
});
