import {useCallback,useEffect,useRef,useState} from 'react';
import {ArrowRight,Check,X} from 'lucide-react';
import {difficultyLabel,type Answer,type Game,type Player,type Question} from './types';
import type {Action} from './commands';
import {ShowHeader} from './ShowHeader';
import {RecognitionPanel} from './RecognitionPanel';

type Props={player:Player;game:Game;question:Question;selected:number|null;feedback:Answer|null;seconds:number;expired:boolean;busy:boolean;settling:'saving'|'accepted'|null;repeat:boolean;error:string;onDismissError:()=>void;onAction:(action:Action)=>boolean;onFinish:()=>Promise<void>};

export function RoundStage(p:Props){
  const {game,question,feedback,selected,seconds,busy,settling}=p;
  const [exitOpen,setExitOpen]=useState(false),dialog=useRef<HTMLDialogElement>(null);
  const action=useRef(p.onAction);action.current=p.onAction;
  const exitActive=useRef(exitOpen);exitActive.current=exitOpen;
  const deviceAction=useCallback((a:Action)=>!exitActive.current&&action.current(a),[]);
  useEffect(()=>{
    const key=(e:KeyboardEvent)=>{
      if(e.repeat||e.altKey||e.ctrlKey||e.metaKey||dialog.current?.open)return;
      const target=e.target as HTMLElement;
      if(target.closest('input,textarea,select,[contenteditable="true"]'))return;
      if(/^[1-4]$/.test(e.key)){e.preventDefault();action.current({type:'select',index:Number(e.key)-1});}
      else if(e.key==='Enter'&&!target.closest('button:not(.answer),a,summary')){e.preventDefault();action.current({type:feedback?'next':'confirm'});}
    };
    window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);
  },[!!feedback]);
  useEffect(()=>{if(exitOpen)dialog.current?.showModal();else dialog.current?.close();},[exitOpen]);
  const phase=feedback?(feedback.timed_out?'timeout':feedback.is_correct?'correct':'incorrect'):settling?'locked':selected===null?'question':'selected';
  const status=feedback?feedback.timed_out?'Время вышло — ответ не подтверждён':feedback.is_correct?'Это правильный ответ!':'Правильный ответ — '+String.fromCharCode(65+feedback.correct):settling==='accepted'?'Ответ принят. Момент истины…':settling==='saving'?'Фиксируем ответ…':p.expired?'Время вышло. Сохраняем результат…':selected===null?'Выберите ответ. Доверьтесь своим знаниям.':`Выбран ответ ${'ABCD'[selected]}. Это ваш окончательный ответ?`;
  return <div className={'show-shell phase-'+phase} data-phase={phase}>
    <ShowHeader nickname={p.player.nickname} disabled={busy} onExit={()=>setExitOpen(true)}/>
    <main className="show-layout">
      <section className="show-play" aria-label="Игровая сцена">
        <div className="show-scoreboard"><div className="show-progress"><div>Вопрос <b>{String(question.number).padStart(2,'0')}</b><span> / {game.total}</span></div><div className="show-steps" aria-label={`Вопрос ${question.number} из ${game.total}`}>{Array.from({length:game.total},(_,i)=><i key={i} className={i<question.number-1?'done':i===question.number-1?'current':''}/>)}</div></div><div className="show-metrics"><span>Счёт <b>{game.xp} <small>XP</small></b></span><span>Серия <b>{game.streak}</b></span></div></div>
        <div className={'show-clock '+(seconds<=10&&!feedback?'urgent':'')+(settling?' frozen':'')} role="timer" aria-label="Время на ответ" data-seconds={seconds}>
          <svg viewBox="0 0 144 144" aria-hidden="true"><circle className="clock-track" cx="72" cy="72" r="67"/><circle className="clock-value" cx="72" cy="72" r="67" pathLength="100" strokeDasharray={`${seconds/30*100} 100`}/></svg><div><b>{seconds}</b><span>{settling==='saving'?'фиксация':settling==='accepted'?'принято':feedback?'завершён':'секунд'}</span></div>
        </div>
        <div key={question.id} className={'show-question question-panel '+(p.repeat?'repeat':'')}>
          <div className="show-meta"><span>{question.category}</span><i aria-hidden="true"/><span>{difficultyLabel[question.difficulty]}</span></div>
          <h1 id="show-question-title">{question.text}</h1>
          <div className="show-answers answers" role="group" aria-labelledby="show-question-title" aria-label="Варианты ответа">{question.options.map((option,i)=>{
            const correct=feedback&&i===feedback.correct,wrong=feedback&&!feedback.is_correct&&i===feedback.selected;
            return <button key={i} disabled={!!feedback||busy||p.expired} aria-pressed={selected===i} className={'answer show-answer '+(selected===i?'selected ':'')+(correct?'correct ':wrong?'incorrect ':'')+(feedback&&!correct&&!wrong?'muted-answer':'')} onClick={()=>p.onAction({type:'select',index:i})}><span className="letter"><b>{'ABCD'[i]}</b></span><span className="answer-copy">{option}</span><span className="show-answer-mark" aria-hidden="true">{correct?<Check size={20}/>:wrong?<X size={20}/>:null}</span></button>;
          })}</div>
          <div className={'show-status '+(feedback?'feedback '+(feedback.is_correct?'good':'bad'):'')} role="status" aria-live="polite"><div className="show-status-title">{settling&&<span className="show-suspense-dots" aria-hidden="true"><i/><i/><i/></span>}<b>{status}</b>{feedback&&<span className="show-xp">+{feedback.xp} XP</span>}</div>{feedback&&<p>{feedback.explanation}</p>}</div>
          <button className="show-confirm" disabled={busy||(!feedback&&(selected===null||p.expired))} onClick={()=>p.onAction({type:feedback?'next':'confirm'})}>{settling==='saving'?'Фиксируем ответ…':settling==='accepted'?'Ответ зафиксирован':busy?'Загружаем…':feedback?(game.answered>=game.total?'Результаты раунда':'Следующий вопрос'):'Подтвердить ответ'}<ArrowRight size={21}/></button>
          <p className="show-shortcuts">1–4 — выбор <span>·</span> Enter — {feedback?'дальше':'подтвердить'}</p>
        </div>
        <p className="show-signature"><span/>Каждый вопрос — новый уровень.<span/></p>
      </section>
      <RecognitionPanel onAction={deviceAction}/>
    </main>
    {p.error&&<div className="show-error" role="alert"><span>{p.error}</span><button onClick={p.onDismissError} aria-label="Закрыть ошибку"><X size={18}/></button></div>}
    <dialog ref={dialog} className="show-dialog" onCancel={()=>setExitOpen(false)} onClose={()=>setExitOpen(false)}><h2>Завершить раунд?</h2><p>Подтверждённые ответы и полученный опыт сохранятся. Пока вы решаете, таймер продолжает идти.</p><button className="show-confirm" onClick={()=>setExitOpen(false)}>Продолжить игру</button><button className="show-exit" disabled={busy} onClick={()=>{setExitOpen(false);void p.onFinish();}}>Завершить раунд</button></dialog>
  </div>;
}
