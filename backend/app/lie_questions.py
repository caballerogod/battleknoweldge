"""Offline truth puzzles with explicit derivations, no model or invented citations."""
import copy,random

# Each triple carries its factual verification. Mathematics is self-contained;
# the astronomy triples reference the reviewed NASA planet fact sheets.
GROUPS=[
 [('У треугольника три стороны.',True,'Это определение треугольника.'),('У квадрата четыре равные стороны.',True,'Это определение квадрата.'),('У куба восемь граней.',False,'У куба 6 граней, 8 — число вершин.')],
 [('Марс называют Красной планетой.',True,'Оксиды железа придают поверхности красноватый цвет. NASA: https://science.nasa.gov/mars/facts/'),('У Марса два спутника.',True,'Фобос и Деймос. NASA: https://science.nasa.gov/mars/facts/'),('Марс ближе к Солнцу, чем Земля.',False,'Марс — четвёртая планета, Земля — третья. NASA: https://science.nasa.gov/mars/facts/')],
 [('Венера горячее Меркурия по средней температуре поверхности.',True,'Плотная атмосфера и парниковый эффект. NASA: https://science.nasa.gov/venus/venus-facts/'),('У Венеры нет естественных спутников.',True,'NASA: https://science.nasa.gov/venus/venus-facts/'),('Венера — самая большая планета Солнечной системы.',False,'Это Юпитер; Венера близка по размеру к Земле. NASA: https://science.nasa.gov/venus/venus-facts/')],
 [('Половина половины пиццы — четверть пиццы.',True,'1/2 × 1/2 = 1/4.'),('Две трети пиццы больше половины.',True,'2/3 = 4/6, 1/2 = 3/6.'),('Если отдать треть пиццы, останется половина.',False,'1 − 1/3 = 2/3, а не 1/2.')],
 [('Число 2 — простое.',True,'Делится только на 1 и на себя.'),('Число 9 — нечётное.',True,'9 не делится на 2 нацело.'),('Любое нечётное число — простое.',False,'9 = 3 × 3 — контрпример.')],
 [('В слове «кот» три буквы.',True,'К, о, т — 3 буквы.'),('«Топот» читается одинаково в обе стороны.',True,'Обратный порядок букв: т, о, п, о, т.'),('В слове «молоко» две буквы «о».',False,'М-о-л-о-к-о: три буквы «о».')],
 [('В двух часах 120 минут.',True,'2 × 60 = 120.'),('В полутора часах 90 минут.',True,'1.5 × 60 = 90.'),('В четверти часа 25 минут.',False,'60 / 4 = 15 минут.')],
 [('Кило означает тысячу.',True,'Префикс кило — множитель 1000 в СИ.'),('В километре тысяча метров.',True,'1 км = 1000 м.'),('В квадратном километре тысяча квадратных метров.',False,'1000 м × 1000 м = 1 000 000 м².')],
 [('Десять процентов от 200 — это 20.',True,'200 × 0.1 = 20.'),('После скидки 50% вещь за 100 стоит 50.',True,'100 − 100 × 0.5 = 50.'),('Скидка 50%, а затем повышение цены на 50% вернут исходную цену.',False,'100 × 0.5 × 1.5 = 75.')],
 [('У обычного шестигранного кубика шесть граней.',True,'В условии указан шестигранный кубик.'),('Сумма очков двух обычных кубиков может быть равна 12.',True,'6 + 6 = 12.'),('Сумма очков двух кубиков 1–6 может быть равна 1.',False,'Минимум: 1 + 1 = 2.')],
]

def lie_rows(reserve=False):
 rows=[]
 positions=[0,1,2,0,1];random.SystemRandom().shuffle(positions)
 for i,group in enumerate(GROUPS[5:] if reserve else GROUPS[:5]):
  facts=[dict(text=t,truth=b,verification=v) for t,b,v in group if b];random.SystemRandom().shuffle(facts)
  t,b,v=next(row for row in group if not row[1]);facts.insert(positions[i],dict(text=t,truth=b,verification=v))
  answer=next(f['text'] for f in facts if not f['truth'])
  rows.append(dict(topic_index=0,price=(i+1)*100,kind='lie',image_id='',question=['Геометрия: найди ложь.','Красная планета: найди ложь.','Венера: найди ложь.','Пицца на троих: найди ложь.','Числа с подвохом: найди ложь.','Поиграем в слова: найди ложь.','Часы спешат: найди ложь.','Размер имеет значение: найди ложь.','Скидки и подвох: найди ложь.','Бросаем кубики: найди ложь.'][i+(5 if reserve else 0)],answer=answer,aliases=[],options=[f['text'] for f in facts],statements=facts,explanation=' '.join(f['verification'] for f in facts),origin='local'))
 return rows

def shuffle_lies(clues):
 topics={q['topic_index'] for q in clues if q.get('kind')=='lie'}
 for topic in topics:
  questions=[q for q in clues if q.get('kind')=='lie' and q['topic_index']==topic]
  positions=([0,1,2]*((len(questions)+2)//3))[:len(questions)];random.SystemRandom().shuffle(positions)
  for q,index in zip(questions,positions):
   facts=q['statements'];false=next(f for f in facts if not f['truth']);true=[f for f in facts if f['truth']];random.SystemRandom().shuffle(true);true.insert(index,false)
   q['statements']=true;q['options']=[f['text'] for f in true]

def validate_lie(q):
 facts=q.get('statements',[])
 if len(facts)!=3 or sum(f.get('truth') is False for f in facts)!=1 or sum(f.get('truth') is True for f in facts)!=2:
  raise ValueError('Нужны два истинных утверждения и одно ложное')
 if [f['text'] for f in facts]!=q.get('options') or len(set(q['options']))!=3 or q['answer']!=next(f['text'] for f in facts if not f['truth']):
  raise ValueError('У Найди ложь должен быть один правильный вариант')
 if any(not isinstance(f.get('verification'),str) or len(f['verification'].strip())<8 for f in facts):
  raise ValueError('Для каждого утверждения нужна проверка')

def replace_unverified(clues,issues=()):
 rejected={(n['topic_index'],n['price']) for n in issues}
 for i,q in enumerate(clues):
  if q.get('kind')!='lie':continue
  try:
   validate_lie(q)
   if (q['topic_index'],q['price']) in rejected:raise ValueError('Unresolved editorial issue')
  except (ValueError,KeyError,TypeError):
   new=copy.deepcopy(lie_rows()[q['price']//100-1]);new['topic_index']=q['topic_index'];clues[i]=new
 return clues
