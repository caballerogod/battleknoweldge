import {useState} from 'react';

export type PresentationTopic={name:string;aliases:string[]};
const normalized=(s:string)=>s.toLocaleLowerCase('ru-RU').replace(/ё/g,'е').replace(/\s+/g,' ').trim();
export function filterTopics(catalog:PresentationTopic[],query:string){
  const q=normalized(query);
  return catalog.filter(t=>[t.name,...t.aliases].some(s=>normalized(s).includes(q)));
}

export function PresentationTopics({catalog,selected,onChange}:{catalog:PresentationTopic[];selected:string[];onChange:(value:string[])=>void}){
  const [query,setQuery]=useState('');
  const matches=filterTopics(catalog,query);
  function toggle(name:string){onChange(selected.includes(name)?selected.filter(t=>t!==name):selected.length<8?[...selected,name]:selected);}
  function randomTopics(){const pool=[...catalog];for(let i=pool.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[pool[i],pool[j]]=[pool[j],pool[i]];}onChange(pool.slice(0,8).map(t=>t.name));}
  return <section className="presentation-picker" aria-label="Темы презентации">
    <div className="presentation-picker-heading"><h2>Выберите 8 общих тем</h2><strong aria-live="polite">Выбрано {selected.length} из 8</strong></div>
    <p>20 тем · 100 основных и 100 резервных вопросов. Подготовка без модели и расходов API.</p>
    <label className="presentation-search">Найти тему<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Например, NBA, парфюм или сериалы"/></label>
    <div className="presentation-selected" aria-label="Выбранные темы">{selected.map((t,i)=><button type="button" key={t} onClick={()=>toggle(t)} aria-label={'Убрать тему '+t}><b>{i+1}</b>{t}<span aria-hidden="true">×</span></button>)}</div>
    <div className="presentation-catalog" role="group" aria-label="Каталог тем">{matches.map(t=><button type="button" key={t.name} aria-pressed={selected.includes(t.name)} disabled={selected.length===8&&!selected.includes(t.name)} onClick={()=>toggle(t.name)}>{t.name}<small>{selected.includes(t.name)?'Выбрана':'5 + 5 вопросов'}</small></button>)}</div>
    {matches.length===0&&<p role="status">Такой темы в подготовленном банке нет. Попробуйте другое название или очистите поиск.</p>}
    <div className="presentation-picker-actions"><button type="button" onClick={randomTopics} disabled={catalog.length<8}>Случайные 8 тем</button><button type="button" onClick={()=>onChange([])} disabled={!selected.length}>Очистить выбор</button></div>
  </section>;
}
