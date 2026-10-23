import {ArrowRight} from 'lucide-react';
import type {Game,Player} from './types';
import {ShowHeader} from './ShowHeader';
export function RoundResults({game,player,busy,onPlay,onMenu,onStats,error,onDismissError}:{game:Game;player:Player;busy:boolean;onPlay:()=>void;onMenu:()=>void;onStats:()=>void;error:string;onDismissError:()=>void}){
  return <div className="show-shell show-results"><ShowHeader nickname={player.nickname} onExit={onMenu} label="На главную" disabled={busy}/><main className="show-results-content">
    <h1>{game.accuracy===100&&game.answered===game.total?'Идеальная битва.':'Битва завершена.'}</h1><p className="show-result-subtitle">Пройдено {game.answered} из {game.total} вопросов</p>
    <div className="show-reward"><span/><strong>+{game.xp}<small> XP</small></strong><span/></div>
    <div className="show-result-metrics"><div><b>{game.correct}</b><span>верно</span></div><div><b>{game.wrong}</b><span>ошибок</span></div><div><b>{game.accuracy}<small>%</small></b><span>точность</span></div></div>
    <p className="show-result-level">Уровень {game.initial_level} <ArrowRight size={22}/> {game.current_level}</p>
    <div className="show-result-categories"><section><h2>Сильные категории</h2><p>{game.strong.join(', ')||'Нужно больше ответов для уверенной оценки'}</p></section><section><h2>Зоны роста</h2><p>{game.weak.join(', ')||'Продолжайте исследовать все категории'}</p></section></div>
    <section className="show-result-achievements"><h2>Достижения раунда</h2><p>{game.achievements.join(' · ')||'Новые достижения ещё впереди'}</p></section>
    <p className="show-recommendation">{game.recommendation}</p><button className="show-confirm" disabled={busy} onClick={onPlay}>{busy?'Подготовка…':'Играть снова'}<ArrowRight size={21}/></button><button className="show-analytics-link" disabled={busy} onClick={onStats}>Открыть аналитику</button>
    {error&&<div className="alert" role="alert">{error}<button aria-label="Закрыть ошибку" onClick={onDismissError}>×</button></div>}
  </main></div>;
}
