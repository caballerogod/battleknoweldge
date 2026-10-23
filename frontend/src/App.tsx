import {useCallback,useEffect,useRef,useState} from 'react';
import {ArrowRight,BookOpen,BrainCircuit,ChartNoAxesColumn,Code2,FlaskConical,Globe2,GraduationCap,LogOut,Play,Sparkles,Trophy,UserRound,Zap} from 'lucide-react';
import {api} from './api';
import {announcer} from './announcer';
import {soundtrack} from './soundtrack';
import {deadlineAnchor} from './countdown';
import {useQuestionTimer} from './useQuestionTimer';
import {canPerform,type Action} from './commands';
import {RoundStage} from './RoundStage';
import {RoundResults} from './RoundResults';
import {GameHub,TriviaEntry} from './GameHub';
import {Trivia} from './Trivia';
import {Achievements,Analytics} from './Analytics';
import {type Achievement,type Answer,type Game,type Player,type Question,type Stats} from './types';

type Screen='hub'|'trivia'|'menu'|'game'|'result'|'profile'|'achievements'|'stats';
const categories=[{name:'Программирование',Icon:Code2,sub:'Логика и технологии'},{name:'Математика',Icon:BrainCircuit,sub:'От чисел к открытиям'},{name:'История',Icon:BookOpen,sub:'Уроки прошлого'},{name:'География',Icon:Globe2,sub:'Открой свою планету'},{name:'Наука',Icon:FlaskConical,sub:'Пойми законы мира'}];
function savedId(){const n=Number(localStorage.getItem('battle.player'));return n>0?n:null;}
export default function App(){
  const [player,setPlayer]=useState<Player|null>(null),[screen,setScreen]=useState<Screen>(()=>new URLSearchParams(location.search).has('party')&&savedId()?'trivia':'hub'),[nickname,setNickname]=useState('');
  const afterLogin=useRef<'menu'|'trivia'>('menu');
  const [game,setGame]=useState<Game|null>(null),[question,setQuestion]=useState<Question|null>(null),[selected,setSelected]=useState<number|null>(null),[feedback,setFeedback]=useState<Answer|null>(null);
  const [stats,setStats]=useState<Stats|null>(null),[achievements,setAchievements]=useState<Achievement[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[ready,setReady]=useState(false),[repeat,setRepeat]=useState(false);
  const lock=useRef(false);
  const [settling,setSettling]=useState<'saving'|'accepted'|null>(null);
  const activeScreen=useRef(screen);activeScreen.current=screen;
  function announceResult(answer:Answer){if(activeScreen.current==='game'){announcer.cancel();announcer.announce(answer.timed_out?'timeout':answer.is_correct?'correct':'incorrect',{pauseMs:0});}}
  const {seconds,expired}=useQuestionTimer(question?.client_deadline??null,screen==='game'&&!!question&&!feedback&&!settling,()=>{if(!lock.current)void submitAnswer(null);});
  useEffect(()=>{soundtrack.setQuestionActive(screen==='game'&&!!question&&!feedback&&!expired);return()=>soundtrack.setQuestionActive(false);},[screen,question?.id,!!feedback,expired]);
  useEffect(()=>{if(screen==='game'&&!feedback&&!settling&&seconds>0&&seconds<=10)void soundtrack.playCue('tick');},[seconds,screen,!!feedback,!!settling]);
  async function run(task:()=>Promise<void>){if(lock.current)return;lock.current=true;setBusy(true);setError('');try{await task();}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);lock.current=false;}}
  useEffect(()=>{const id=savedId();if(!id){setReady(true);return;}void run(async()=>{try{const s=await api<Stats>(`/players/${id}/stats`);setPlayer(s.player);setStats(s);}catch(e){if(e instanceof Error&&e.message.includes('не найдены'))localStorage.removeItem('battle.player');throw e;}finally{setReady(true);}});},[]);
  useEffect(()=>{if(screen!=='game')announcer.cancel();},[screen]);
  useEffect(()=>()=>announcer.cancel(),[]);
  async function login(){await run(async()=>{const p=await api<Player>('/players',{nickname});localStorage.setItem('battle.player',String(p.id));setPlayer(p);setStats(await api<Stats>(`/players/${p.id}/stats`));setScreen(afterLogin.current);});}
  async function loadQuestion(g:Game){const q=await api<Question>(`/sessions/${g.id}/next`,{});q.client_deadline=deadlineAnchor(q.deadline_at,q.server_time,performance.now());setQuestion(q);setSelected(null);setFeedback(null);setSettling(null);}
  async function start(){if(!player)return;await run(async()=>{const g=await api<Game>('/sessions',{player_id:player.id});setGame(g);
    if(g.answered>=g.total){const result=await api<Game>(`/sessions/${g.id}/finish`,{});setGame(result);setScreen('result');return;}
    await loadQuestion(g);setScreen('game');if(g.answered===0&&g.pending_id===null)announcer.announce('round-start');});}
  async function confirm(){if(selected===null||expired)return;await submitAnswer(selected);}
  async function submitAnswer(choice:number|null){if(!game||!question||feedback)return;await run(async()=>{
    const started=performance.now();setSettling('saving');announcer.cancel();
    // POST immediately. Only presentation waits, never server acceptance or the deadline.
    const reveal=async(answer:Answer,session:Game,updatedPlayer:Player)=>{
      setSettling('accepted');
      await new Promise<void>(resolve=>setTimeout(resolve,Math.max(0,1150-(performance.now()-started))));
      setFeedback(answer);setSelected(answer.selected);setGame(session);setPlayer(updatedPlayer);announceResult(answer);
    };
    try{const result=await api<{answer:Answer;session:Game;player:Player}>(`/sessions/${game.id}/answers`,{question_id:question.id,selected:choice});await reveal(result.answer,result.session,result.player);}
    catch(error){
      // A response can be lost after the server commits. Reconcile before retrying.
      const stored=await api<Game>(`/sessions/${game.id}`).catch(()=>null);
      if(stored?.last_answer?.question_id===question.id){await reveal(stored.last_answer,stored,await api<Player>(`/players/${game.player_id}`));}
      else throw error;
    }
    finally{setSettling(null);}
  });}
  async function next(){if(!game||!feedback)return;await run(async()=>{if(game.answered>=game.total){setGame(await api<Game>(`/sessions/${game.id}/finish`,{}));setScreen('result');}else await loadQuestion(game);});}
  async function finish(){if(!game)return;await run(async()=>{setGame(await api<Game>(`/sessions/${game.id}/finish`,{}));setScreen('result');setPlayer(await api<Player>(`/players/${game.player_id}`));});}
  async function navigate(target:Screen){if(!player){setScreen('menu');return;}await run(async()=>{if(target==='achievements')setAchievements(await api<Achievement[]>(`/players/${player.id}/achievements`));else {const s=await api<Stats>(`/players/${player.id}/stats`);setStats(s);setPlayer(s.player);if(target==='profile')setAchievements(await api<Achievement[]>(`/players/${player.id}/achievements`));}setScreen(target);});}
  function selectAnswer(index:number){setSelected(index);void soundtrack.playCue('select');}
  function action(a:Action){if(!canPerform(a,{selected,answered:!!feedback,busy:busy||lock.current||expired,hasQuestion:!!question}))return false;
    if(a.type==='select')selectAnswer(a.index);else if(a.type==='confirm')void confirm();else if(a.type==='next')void next();else if(a.type==='repeat'&&question){setRepeat(true);setTimeout(()=>setRepeat(false),1200);announcer.say(question.text+'. '+question.options.map((v,i)=>`${i+1}: ${v}`).join('. '),'question');}return true;}
  const controlAction=useRef(action);controlAction.current=action;
  const handleControlAction=useCallback((a:Action)=>controlAction.current(a),[]);
  const titles:Record<Screen,string>={hub:'Выбор игры',trivia:'Своя игра',menu:'Битва знаний',game:'Битва знаний',result:'Итоги битвы',profile:'Мой профиль',achievements:'Достижения',stats:'Статистика'};
  if(ready&&screen==='hub')return <GameHub player={player} busy={busy} onTrivia={()=>{afterLogin.current='trivia';setScreen(player?'trivia':'menu');}} onBattle={()=>{afterLogin.current='menu';setScreen('menu');}} onProfile={()=>{afterLogin.current='menu';if(player)void navigate('profile');else setScreen('menu');}}/>;
  if(ready&&!player&&screen==='menu'&&afterLogin.current==='trivia')return <TriviaEntry nickname={nickname} onChange={setNickname} busy={busy} error={error} onSubmit={()=>void login()} onBack={()=>setScreen('hub')}/>;
  if(screen==='trivia'&&player)return <Trivia player={player} onExit={()=>setScreen('hub')}/>;
  if(screen==='game'&&player&&game&&question)return <RoundStage player={player} game={game} question={question} selected={selected} feedback={feedback} seconds={seconds} expired={expired} busy={busy} settling={settling} repeat={repeat} error={error} onDismissError={()=>setError('')} onAction={handleControlAction} onFinish={finish}/>;
  if(screen==='result'&&player&&game)return <RoundResults game={game} player={player} busy={busy} onPlay={()=>void start()} onMenu={()=>void navigate('menu')} onStats={()=>void navigate('stats')} error={error} onDismissError={()=>setError('')}/>;
  return <div className="app-shell"><aside className="sidebar"><a className="brand" href="#" onClick={e=>{e.preventDefault();setScreen('menu');}}><div className="brand-mark">◇</div><span>AI<br/><b>Knowledge<br/>Battle</b></span></a>
    <nav aria-label="Основная навигация">{([{key:'hub',label:'Выбор игры',Icon:Zap},{key:'profile',label:'Мой профиль',Icon:UserRound},{key:'achievements',label:'Достижения',Icon:Trophy},{key:'stats',label:'Статистика',Icon:ChartNoAxesColumn}] as const).map(({key,label,Icon})=><button key={key} aria-label={label} title={label} className={(screen===key||(key==='hub'&&['menu','game','result'].includes(screen)))?'active':''} onClick={()=>void navigate(key)} disabled={busy}><Icon size={20}/><span>{label}</span></button>)}</nav>
    <div className="sidebar-bottom"><div className="avatar"><GraduationCap size={22}/></div><div><b>{player?.nickname??'Гость'}</b><small>{player?`Уровень ${player.level} · ${player.title}`:'Ваша история начинается здесь'}</small></div>{player&&screen!=='game'&&<button className="icon-button" title="Сменить игрока" aria-label="Сменить игрока" onClick={()=>{localStorage.removeItem('battle.player');setPlayer(null);setStats(null);setGame(null);setQuestion(null);setScreen('menu');}}><LogOut size={16}/></button>}</div>
  </aside><main><header className="page-header"><div><h1>{screen==='menu'||screen==='game'?<>Битва <em>знаний</em></>:titles[screen]}</h1><p>Развивай знания. Управляй голосом и жестами.</p></div>{player&&<div className="level-widget"><div><b>Уровень {player.level}</b><span>{player.xp} / {player.next_level_xp} XP</span></div><div className="bar"><i style={{width:player.level_progress+'%'}}/></div></div>}</header>
  {error&&<div className="alert" role="alert">{error} <button onClick={()=>setError('')} aria-label="Закрыть ошибку">×</button></div>}
  {!ready?<div className="panel loading">Загрузка профиля…</div>:!player?<section className="panel welcome"><div className="welcome-symbol"><BrainCircuit size={60}/></div><h2>Твои знания — <em>твоя сила</em></h2><p>Пять категорий. Десять вопросов. Три способа управления.<br/>Войди в арену и открой, на что способен твой интеллект.</p><form onSubmit={e=>{e.preventDefault();void login();}}><label htmlFor="nickname">Имя игрока</label><input id="nickname" value={nickname} onChange={e=>setNickname(e.target.value)} placeholder="Придумайте никнейм" maxLength={40} required autoComplete="nickname"/><button className="primary" disabled={busy||!nickname.trim()} type="submit">Войти в арену <ArrowRight size={18}/></button></form><small>Никнейм сохраняет ваш прогресс на этом компьютере.<br/>Для возвращения используйте то же имя с учётом регистра.</small></section>:
  screen==='menu'?<><section className="panel hero"><div><div className="hero-symbol"><BrainCircuit size={72}/></div><h2>Твои знания —<br/><em>твоя сила.</em></h2><p>Каждая битва делает тебя сильнее.<br/>Вопросы подстраиваются под твои знания.</p><button className="primary" disabled={busy} onClick={()=>void start()}><Play size={18} fill="currentColor"/>{stats?.active_session?'Продолжить игру':'Начать игру'}<ArrowRight size={20}/></button><small>10 вопросов · адаптивная сложность · 30 секунд на вопрос</small></div><div className="arena-art" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="arena-core"><BrainCircuit size={96}/></div><span className="art-star">✧</span></div></section>
  <div className="category-strip">{categories.map(({name,Icon,sub})=><div key={name}><Icon size={27}/><b>{name}</b><small>{sub}</small></div>)}</div><section className="panel rules"><Sparkles size={24}/><div><h3>Три способа. Одна битва.</h3><p>Выберите A–D мышью, голосом или жестом, затем подтвердите ответ. Получайте 10 / 20 / 30 XP по сложности и +30 XP за каждые пять верных ответов подряд. Камера и микрофон включаются только по вашему желанию.</p></div></section></>:
  screen==='achievements'?<><p className="section-intro">Знаки твоего прогресса. Каждое достижение выдаётся один раз.</p><Achievements items={achievements}/></>:
  stats?<>{screen==='profile'&&<section className="panel profile-banner"><div className="avatar large"><GraduationCap size={36}/></div><div><h2>{player.nickname}</h2><p>Уровень {player.level} · {player.title}</p></div><button className="secondary" onClick={()=>void navigate('achievements')}><Trophy size={17}/> Мои достижения</button></section>}<Analytics stats={stats} history={true}/>{screen==='profile'&&<><h2 className="section-intro">Полученные достижения</h2><Achievements items={achievements.filter(a=>a.earned_at)}/>{!achievements.some(a=>a.earned_at)&&<p className="section-intro">Сделайте первый шаг: ответьте верно на вопрос.</p>}</>}</>:null}
  <footer>AI Knowledge Battle <span>Учись. Исследуй. Побеждай.</span></footer></main></div>;
}


