import {describe,expect,it} from 'vitest';
import {boardSelection,FingerHold,fingerCount} from './triviaCommands';
const topics=['Космос','История Казахстана','Гарри Поттер','Футбол','Python'];
describe('board voice commands',()=>{
  it.each([['Космос за триста',{topic:0,price:300}],['История Казахстана, пятьсот.',{topic:1,price:500}],['Третья тема за двести',{topic:2,price:200}],['тема 5 за 100',{topic:4,price:100}],['ВТОРАЯ ТЕМА',{topic:1}],['четыреста очков',{price:400}],['Python 500',{topic:4,price:500}]])('parses %s',(phrase,result)=>expect(boardSelection(phrase as string,topics)).toEqual(result));
  it.each(['Космос за шестьсот','первая или вторая за сто','Космос и Футбол за 100','не знаю','Меркурий','Космос за 300 или 500'])('does not guess ambiguous commands: %s',phrase=>expect(boardSelection(phrase,topics)).toBeNull());
});
describe('five-position gestures',()=>{
  it('emits each stable pose once and requires release to repeat the same number',()=>{
    const gate=new FingerHold();expect(gate.update(3,0)).toBeNull();expect(gate.update(3,799)).toBeNull();expect(gate.update(3,800)).toBe(3);expect(gate.update(3,2000)).toBeNull();gate.update(null,2100);gate.update(null,2400);expect(gate.update(3,2500)).toBeNull();expect(gate.update(3,3300)).toBe(3);
  });
  it('a different pose can select the next step, including the fifth option',()=>{const g=new FingerHold();g.update(1,0);expect(g.update(1,800)).toBe(1);g.update(5,1000);expect(g.update(5,1800)).toBe(5);});
  it('invalid or implausibly small hands cannot select a cell',()=>{expect(fingerCount(undefined)).toBeNull();expect(fingerCount([])).toBeNull();expect(fingerCount(Array.from({length:21},()=>({x:0,y:0})))).toBeNull();});
  it.each([1,2,3,4,5])('counts %s fingers independently of mirroring and rotation',(n)=>{
    const hand=Array.from({length:21},()=>({x:0,y:.7,z:0}));hand[0]={x:.5,y:.9,z:0};
    let finger=0;for(const [m,p,t,x] of [[5,6,8,.35],[9,10,12,.45],[13,14,16,.55],[17,18,20,.65]]){hand[m]={x,y:.65,z:0};hand[p]={x,y:.5,z:0};hand[t]={x,y:finger++<n?.25:.67,z:0};}
    hand[2]={x:.3,y:.7,z:0};hand[3]={x:n===5?.2:.35,y:.65,z:0};hand[4]={x:n===5?.1:.45,y:n===5?.6:.7,z:0};
    expect(fingerCount(hand)).toBe(n);expect(fingerCount(hand.map(p=>({x:1-p.x,y:p.y,z:0})))).toBe(n);expect(fingerCount(hand.map(p=>({x:p.y,y:1-p.x,z:0})))).toBe(n);
  });
});

describe('eight shared topics',()=>{
  const eight=[...topics,'Мемы','Баскетбол','Кино'];
  it.each([['Шестая тема за триста',{topic:5,price:300}],['седьмая за сто',{topic:6,price:100}],['восьмая тема за пятьсот',{topic:7,price:500}],['тема 8 за 200',{topic:7,price:200}]])('parses %s',(text,result)=>expect(boardSelection(text as string,eight)).toEqual(result));
  it('rejects unavailable topic nine',()=>expect(boardSelection('девятая тема за сто',eight)).toBeNull());
});
