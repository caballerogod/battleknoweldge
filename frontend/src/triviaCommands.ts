const clean=(s:string)=>s.toLocaleLowerCase('ru-RU').replaceAll('ё','е').replace(/[^\p{L}\p{N}\s]/gu,' ').replace(/\s+/g,' ').trim();
const ordinals=[['1','первая','первую','первый'],['2','вторая','вторую','второй'],['3','третья','третью','третий'],['4','четвертая','четвертую','четвертый'],['5','пятая','пятую','пятый'],['6','шестая','шестую','шестой'],['7','седьмая','седьмую','седьмой'],['8','восьмая','восьмую','восьмой']];
const prices:Record<string,number>={'100':100,'200':200,'300':300,'400':400,'500':500,сто:100,двести:200,триста:300,четыреста:400,пятьсот:500};
export function boardSelection(phrase:string,topics:string[]):{topic?:number;price?:number}|null{
  const t=clean(phrase).replace(/^(?:выбрать|выбери) /,'');
  const match=t.match(/^(.*?)(?:\s+за\s+|\s+)?(100|200|300|400|500|сто|двести|триста|четыреста|пятьсот)(?:\s+очк(?:ов|а|о))?$/);
  const subject=(match?match[1]:t).trim().replace(/^тема\s+|\s+тема$/g,'');
  const topic=topics.findIndex((name,i)=>clean(name)===subject||ordinals[i]?.includes(subject));
  const price=match?prices[match[2]]:undefined;
  if(subject&&topic<0)return null;
  if(topic<0&&price===undefined)return null;
  return {...(topic>=0?{topic}:{}),...(price?{price}:{})};
}
type Point={x:number;y:number;z?:number};
const dist=(a:Point,b:Point)=>Math.hypot(a.x-b.x,a.y-b.y,(a.z??0)-(b.z??0));
function straight(a:Point,b:Point,c:Point){
  const ab=[a.x-b.x,a.y-b.y,(a.z??0)-(b.z??0)],cb=[c.x-b.x,c.y-b.y,(c.z??0)-(b.z??0)];
  const length=Math.hypot(...ab)*Math.hypot(...cb);return length>1e-7&&ab.reduce((sum,v,i)=>sum+v*cb[i],0)/length<-.7;
}
/** Geometry is rotation/mirror independent; it is not a claimed classifier confidence. */
export function fingerCount(hand:Point[]|undefined):number|null{
  if(!hand||hand.length!==21||hand.some(p=>![p.x,p.y,p.z??0].every(Number.isFinite)))return null;
  const palm=dist(hand[0],hand[9]);if(palm<.025)return null;
  let count=0;
  for(const [m,p,t] of [[5,6,8],[9,10,12],[13,14,16],[17,18,20]])if(straight(hand[m],hand[p],hand[t])&&dist(hand[t],hand[0])>dist(hand[p],hand[0])*1.12)count++;
  if(straight(hand[2],hand[3],hand[4])&&dist(hand[4],hand[5])>palm*.55&&dist(hand[4],hand[17])>dist(hand[3],hand[17])*1.08)count++;
  return count>=1&&count<=5?count:null;
}
export class FingerHold{
  private candidate:number|null=null;private since=0;private fired=false;private missing:number|null=null;
  progress=0;
  update(count:number|null,time:number):number|null{
    if(count===null){this.missing??=time;if(time-this.missing>250){this.candidate=null;this.fired=false;this.progress=0;}return null;}
    this.missing=null;
    if(count!==this.candidate){this.candidate=count;this.since=time;this.fired=false;this.progress=0;}
    this.progress=Math.min(1,(time-this.since)/800);
    if(!this.fired&&this.progress===1){this.fired=true;return count;}
    return null;
  }
}
