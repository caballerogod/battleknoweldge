import {useEffect,useRef,useState} from 'react';
import {api} from './api';
type Sheet={id:string;topics:{name:string;questions:{cell:number;price:number;question:string;answer:string;aliases:string[];options:string[];explanation:string;host_review:boolean;review_note:string}[]}[]};
/** Answers are fetched only after the host explicitly opens this view. */
export function HostAnswers({gameId,onClose}:{gameId:string;onClose:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null);
 const [sheet,setSheet]=useState<Sheet|null>(null),[error,setError]=useState('');
 useEffect(()=>{dialog.current?.showModal();let cancelled=false;void api<Sheet>(`/trivia/games/${gameId}/host-sheet`).then(value=>{if(!cancelled)setSheet(value);}).catch(e=>{if(!cancelled)setError(e instanceof Error?e.message:String(e));});return()=>{cancelled=true;};},[gameId]);
 return <dialog ref={dialog} className="host-answers" aria-labelledby="host-answers-title" onCancel={onClose}>
  <header><div><h2 id="host-answers-title">Ответы для ведущего</h2><p>Здесь все ответы. Скрывайте этот раздел от игроков.</p></div><button autoFocus onClick={onClose}>Скрыть ответы</button></header>
  {error?<p role="alert">{error}</p>:!sheet?<p role="status">Загружаем ответы…</p>:<><p>{sheet.topics.reduce((count,t)=>count+t.questions.length,0)} вопросов · {sheet.topics.length} тем. Ответы сохранены вместе с партией.</p>{sheet.topics.map((topic,t)=><section key={t}><h3>{t+1}. {topic.name}</h3>{topic.questions.map(q=><article key={q.cell}><span>{q.price} очков</span><h4>{q.question}</h4>{q.options.length>0&&<p>Варианты: {q.options.join(' · ')}</p>}<p><strong>{q.host_review?'Предложенный ответ':'Ответ'}: {q.answer.replaceAll(';','; ')}</strong></p>{q.aliases.length>0&&<p>Также принимаются: {q.aliases.join(', ')}</p>}<p>{q.explanation}</p>{q.host_review&&<p className="host-answer-note">Нужна оценка ведущего: {q.review_note}</p>}</article>)}</section>)}</>}
 </dialog>;
}
