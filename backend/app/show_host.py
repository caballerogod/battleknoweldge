"""Local, persisted host events. No network is needed for the default presenter."""
import json

LINES={
 'game_started':['{names}, добро пожаловать! Сегодня выигрывают смелость и немного удачи.','Наши участники: {names}. Знакомьтесь с будущими легендами вечера!'],
 'question_opened':['{name}, вопрос за {price}. Ловим момент!','На кону {price}. {name}, твой выход!'],
 'correct_answer':['{name}, красиво! Плюс {price}.','Вот это попадание, {name}!'],
 'wrong_answer':['{name}, смелая версия. Реальность возражает!','Бывает, {name}. Следующий заход может всё изменить.'],
 'steal_started':['Вопрос свободен! Кто заберёт эти очки?','Внимание: открыт перехват!'],
 'steal_success':['{name} забирает чужой вопрос! Вот это манёвр!','Перехват сработал! {name}, плюс {price}.'],
 'steal_failed':['Перехват не зашёл. Но интрига ещё жива!','Риск был красивым. Ответ — чуть менее точным.'],
 'streak_reached':['Три подряд, {name}! Кто-нибудь его остановит?','{name}, три попадания подряд. Пошла жара!'],
 'leader_changed':['А вот и переворот! {name} выходит вперёд!','Новый лидер — {name}. Держим интригу!'],
 'final_started':['Поле закончено. Но всё решится в Последней битве!','Счёт — только начало. Время решающих ставок!'],
 'final_results':['Ставки раскрываются. Смотрим, кто был точнее!','Финал отвечает за себя. Считаем очки!'],
 'game_finished':['Поздравляем: {names}! Вот это был вечер!','Наши победители: {names}. Аплодисменты!']}

def state(g):return json.loads(g.show_state or '{}')
def save(g,s):g.show_state=json.dumps(s,ensure_ascii=False)
def options(g):return state(g).get('options',{})
def emit(g,event,**values):
 s=state(g);opts=s.get('options',{})
 if opts.get('host','off')=='off':return
 names=json.loads(g.participants or '[]');data=dict(name=names[values.get('participant',0)] if names else 'Игрок',names=', '.join(names),price=values.get('price',0));data.update(values)
 events=s.setdefault('events',[]);number=s.get('event_number',0)+1;s['event_number']=number
 persona=opts.get('persona','friendly');templates=LINES.get(event,['Игра продолжается.'])
 counts=s.setdefault('template_counts',{});count=counts.get(event,0);counts[event]=count+1
 line=templates[count%len(templates)].format(**data)
 if persona=='serious':line={'game_started':f"Участники: {data['names']}. Начинаем игру.",'question_opened':f"{data['name']}, вопрос за {data['price']} очков.",'wrong_answer':'Ответ неверный.','correct_answer':f"Верный ответ. Начислено {data['price']} очков."}.get(event,line)
 elif persona=='bold' and event=='question_opened':line+= ' Проверим, кто тут босс!'
 events.append(dict(id=number,event=event,text=line,participant=values.get('participant')));s['events']=events[-30:];save(g,s)
