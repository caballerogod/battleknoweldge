import copy,json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import create_app
from app.models import TriviaGame
from app.presentation_bank import presentation_pack
from app.quiz_ai import OpenAIQuiz,strict_schema,MixedPack,EditorialReview
from app.show_rules import FinalClue,HostLine
from app.lie_questions import lie_rows,validate_lie
from app.show_host import emit,state

TOPICS=['Найди ложь','Еда','Мемы','Космос','Музыка','География','Кино','Да или Нет']
class FakeAI(OpenAIQuiz):
 calls=[]
 @property
 def configured(self):return True
 def generate(self,topics,**kwargs):return presentation_pack(topics)[0]
 def request(self,instructions,data,schema,tokens):
  self.calls.append((schema,tokens))
  if schema is FinalClue:return dict(question='Сколько будет два плюс три, если считаем обычные целые числа?',answer='5',aliases=['пять'],explanation='Два плюс три равно пяти, обычное сложение целых чисел.')
  if schema is HostLine:
   assert data['persona'] in {'friendly','bold','serious'}
   return {'text':'Вот это поворот. Игра продолжается!'}
  raise AssertionError('No external calls')
 def grade(self,*args):raise AssertionError('Use exact answers or host verdict')

@pytest.fixture
def stage(tmp_path):
 clock=[1000.];ai=FakeAI();ai.calls=[];url=f'sqlite:///{tmp_path/"show.db"}'
 app=create_app(url,clock=lambda:clock[0],quiz_provider=ai)
 with TestClient(app) as c:
  player=c.post('/api/players',json={'nickname':'Show QA'}).json()
  def create(opts=None,presentation=True):
   payload=dict(player_id=player['id'],request_id=str(uuid4()),topics=TOPICS,participants=['Рашид','Арман','Данияр'],presentation=presentation)
   if opts is not None:payload['show']=opts
   r=c.post('/api/trivia/games',json=payload);assert r.status_code==200,r.text
   g=c.get('/api/trivia/games/'+r.json()['id']).json()
   with Session(app.state.engine) as db:pack=json.loads(db.get(TriviaGame,g['id']).pack)
   return '/api/trivia/games/'+g['id'],pack
  yield c,app,clock,ai,create,url

def answer(c,path,value,cell=4):
 pending=c.get(path).json()['pending']
 return c.post(path+'/answer',json=dict(cell=cell,answer=value,attempt_token=pending.get('attempt_token')))

def test_steal_two_opponents_scores_privacy_and_stale_attempt(stage):
 c,app,clock,ai,create,_=stage;path,pack=create({'steal':True,'host':'text'})
 opened=c.post(path+'/open',json={'cell':4}).json();old=opened['pending']['attempt_token']
 wrong=next(v for v in pack[4]['options'] if v!=pack[4]['answer'])
 g=answer(c,path,wrong).json()
 assert g['played']==0 and g['participants'][0]['score']==-500 and g['pending']['steal']['eligible']==[1,2]
 assert 'correct_answer' not in g['pending'] and 'explanation' not in g['pending'] and not g['results']
 assert c.post(path+'/answer',json={'cell':4,'answer':pack[4]['answer'],'attempt_token':old}).status_code==409
 assert c.post(path+'/steal/claim',json={'cell':4,'participant':0}).status_code==409
 g=c.post(path+'/steal/claim',json={'cell':4,'participant':1}).json();assert g['pending']['deadline']==1015
 clock[0]+=2
 assert c.post(path+'/steal/claim',json={'cell':4,'participant':1}).json()['pending']['deadline']==1015
 assert c.post(path+'/steal/claim',json={'cell':4,'participant':2}).status_code==409
 g=answer(c,path,wrong).json();assert [p['score'] for p in g['participants']]==[-500,-250,0]
 assert g['pending']['steal']['eligible']==[2] and 'correct_answer' not in g['pending']
 assert c.post(path+'/steal/claim',json={'cell':4,'participant':1}).status_code==409
 c.post(path+'/steal/claim',json={'cell':4,'participant':2})
 g=answer(c,path,pack[4]['answer']).json()
 assert [p['score'] for p in g['participants']]==[-500,-250,500] and g['current_participant']==1
 assert g['played']==1 and g['pending'] is None and len(g['results'][0]['attempts'])==3
 assert g['results'][0]['correct_answer']==pack[4]['answer']
 assert answer_repeat(c,path,pack[4]['answer'],old)['participants']==g['participants']
 assert {'steal_started','steal_failed','steal_success'}<={e['event'] for e in g['show']['events']}
 assert ai.calls==[]

def answer_repeat(c,path,value,token):return c.post(path+'/answer',json={'cell':4,'answer':value,'attempt_token':token}).json()

@pytest.mark.parametrize('timeout',[False,True])
def test_decline_and_timeout_do_not_reveal_early(stage,timeout):
 c,_,clock,_,create,_=stage;path,pack=create({'steal':True})
 c.post(path+'/open',json={'cell':4});wrong=next(v for v in pack[4]['options'] if v!=pack[4]['answer']);answer(c,path,wrong)
 if timeout:
  c.post(path+'/steal/claim',json={'cell':4,'participant':1});clock[0]+=15
  g=answer(c,path,pack[4]['answer']).json();assert g['pending']['steal']['eligible']==[2]
  assert g['participants'][1]['score']==0
 else:
  g=c.post(path+'/steal/decline',json={'cell':4,'participant':1}).json()
 assert 'correct_answer' not in g['pending']
 g=c.post(path+'/steal/decline',json={'cell':4,'participant':2}).json()
 assert g['played']==1 and g['results'][0]['correct_answer']==pack[4]['answer'] and g['score']==-500

def complete_board(c,path,pack):
 for i,q in enumerate(pack):
  c.post(path+'/open',json={'cell':i})
  r=answer(c,path,q['answer'],i);assert r.status_code==200,r.text
 return c.get(path).json()

@pytest.mark.parametrize('mode',['host','interface'])
def test_final_bets_privacy_scoring_restart_and_ties(stage,mode):
 c,app,clock,ai,create,dburl=stage;path,pack=create({'final':True,'comeback':True,'final_mode':mode,'host':'text'})
 g=complete_board(c,path,pack);assert g['show']['phase']=='final_bets' and g['status']=='ready'
 before=[p['score'] for p in g['participants']]
 assert c.post(path+'/open',json={'cell':0}).status_code==409
 assert c.post(path+'/final/bet',json={'participant':0,'amount':1001}).status_code==422
 for i in range(3):
  r=c.post(path+'/final/bet',json={'participant':i,'amount':500});assert r.status_code==200,r.text
 assert c.post(path+'/final/bet',json={'participant':0,'amount':400}).status_code==409
 assert c.post(path+'/final/bet',json={'participant':0,'amount':500}).status_code==200
 g=c.get(path).json();assert g['show']['phase']=='final_ready'
 assert 'question' not in g['show']['final'] and 'bets' not in g['show']['final']
 g=c.post(path+'/final/open').json();deadline=g['show']['final']['deadline'];assert deadline==1060
 clock[0]+=12;assert c.post(path+'/final/open').json()['show']['final']['deadline']==deadline
 if mode=='interface':
  for i in range(3):
   g=c.post(path+'/final/answer',json={'participant':i,'answer':'секрет '+str(i)}).json()
   assert 'answers' not in g['show']['final'] and 'bets' not in g['show']['final']
   if i<2:assert 'correct_answer' not in g['show']['final']
 else:g=c.post(path+'/final/close').json()
 assert g['show']['phase']=='final_judging'
 app.state.initialize();assert c.get(path).json()['show']['phase']=='final_judging'
 for i,decision in enumerate(['correct','incorrect','ambiguous']):
  assert c.post(path+'/final/judge',json={'participant':i,'decision':decision}).status_code==200
 for i in range(3):
  g=c.post(path+'/final/reveal',json={'index':i}).json()
  assert len(g['show']['final']['revealed'])==i+1
  again=c.post(path+'/final/reveal',json={'index':i}).json();assert again['participants']==g['participants']
 assert [p['score'] for p in g['participants']]==[before[0]+500,before[1]-500,before[2]]
 assert g['status']=='finished' and g['show']['final']['winners']==[i for i,p in enumerate(g['participants']) if p['score']==max(x['score'] for x in g['participants'])]
 assert ai.calls==[]

def test_lie_validation_and_local_bank():
 for reserve in (False,True):
  rows=lie_rows(reserve);assert len(rows)==5
  for q in rows:validate_lie(q)
  bad=copy.deepcopy(rows[0]);bad['statements'][0]['truth']=False;bad['statements'][1]['truth']=False
  with pytest.raises(ValueError):validate_lie(bad)
  bad=copy.deepcopy(rows[0]);bad['answer']='Другой ответ'
  with pytest.raises(ValueError):validate_lie(bad)
  bad=copy.deepcopy(rows[0]);bad['statements'][0]['verification']=''
  with pytest.raises(ValueError):validate_lie(bad)
 schema=strict_schema(MixedPack)
 assert set(schema['$defs']['MixedClue']['required'])==set(schema['$defs']['MixedClue']['properties'])

def test_host_local_variety_and_opt_in_ai_budget(stage):
 c,app,clock,ai,create,_=stage;path,pack=create({'host':'text','ai_comments':True},presentation=False)
 sid=path.rsplit('/',1)[1]
 with Session(app.state.engine) as db:
  g=db.get(TriviaGame,sid)
  emit(g,'question_opened',price=100);one=state(g)['events'][-1]['text'];emit(g,'question_opened',price=100);two=state(g)['events'][-1]['text'];assert one!=two
  db.commit()
 for _ in range(5):
  with Session(app.state.engine) as db:g=db.get(TriviaGame,sid);emit(g,'leader_changed');db.commit()
  eid=c.get(path).json()['show']['events'][-1]['id']
  assert c.post(path+'/host-comment',json={'event_id':eid}).status_code==200
  clock[0]+=60
 assert len(ai.calls)==3 and all(tokens==256 for _,tokens in ai.calls)
 assert sum(bool(e.get('ai')) for e in c.get(path).json()['show']['events'])==3

def test_legacy_rules_do_not_enable_steal_or_final(stage):
 c,_,_,_,create,_=stage;path,pack=create()
 c.post(path+'/open',json={'cell':4});wrong=next(v for v in pack[4]['options'] if v!=pack[4]['answer'])
 g=answer(c,path,wrong).json();assert g['played']==1 and not g['pending'] and g['score']==-500 and not g['show']['options']

def test_ai_lie_generation_and_unverified_triple_replacement(monkeypatch):
 from app.quiz_ai import ReviewedClues
 pack=presentation_pack(TOPICS)[0]
 for q in pack:
  if q['kind']=='lie':q['origin']='ai'
 plan=[{k:q[k] for k in ('topic_index','price','kind','image_id')} for q in pack]
 monkeypatch.setattr('app.quiz_ai.format_plan',lambda _:plan)
 monkeypatch.setattr('app.quiz_ai.obvious_issues',lambda *args:[])
 calls=[]
 def request(self,instructions,data,schema,tokens):
  calls.append(schema)
  if schema is MixedPack:
   assert 'statements' in instructions
   return {'clues':copy.deepcopy(pack)}
  if schema is EditorialReview:return {'issues':[]}
  raise AssertionError('Unexpected model call')
 monkeypatch.setattr(OpenAIQuiz,'request',request)
 result=OpenAIQuiz().generate(TOPICS)
 assert calls==[MixedPack,EditorialReview]
 assert len(result)==40 and all(q['origin']=='ai' for q in result[:5])
 result[0]['statements']=[dict(f,truth=True) for f in result[0]['statements']]
 reviewed=ReviewedClues(result,[dict(topic_index=0,price=100,reason='Unverified fact')])
 assert reviewed[0]['origin']=='local' and not reviewed.editorial_notes
 validate_lie(reviewed[0])

def test_final_ai_question_without_paid_calls_and_timeout(stage):
 c,app,clock,ai,create,_=stage;path,pack=create({'final':True,'final_mode':'interface'},presentation=False)
 complete_board(c,path,pack)
 for i in range(3):c.post(path+'/final/bet',json={'participant':i,'amount':0})
 assert ai.calls==[(FinalClue,1800)]
 c.post(path+'/final/open')
 assert c.get(path).json()['show']['final']['source']=='ai'
 assert c.post(path+'/final/close').status_code==409
 assert c.post(path+'/final/answer',json={'participant':0,'answer':' '}).status_code==422
 c.post(path+'/final/answer',json={'participant':0,'answer':'first'})
 c.post(path+'/final/answer',json={'participant':0,'answer':'replacement'})
 clock[0]+=60
 g=c.post(path+'/final/close').json();assert g['show']['phase']=='final_judging'
 host=c.get(path+'/final/host').json();assert host['answers']=={'0':'first','1':'','2':''}

def test_final_tie_and_negative_score_bet_limit(stage):
 c,app,clock,ai,create,_=stage;path,pack=create({'final':True})
 from app.show_rules import start_final
 with Session(app.state.engine) as db:
  g=db.get(TriviaGame,path.rsplit('/',1)[1]);g.results=json.dumps([dict(cell=0,participant=0,decision='incorrect',delta=-100,answer='',correct_answer=pack[0]['answer'],question=pack[0]['question'],explanation='Test')]);start_final(g);db.commit()
 assert c.get(path).json()['show']['final']['limits']==[0,0,0]
 assert c.post(path+'/final/bet',json={'participant':0,'amount':1}).status_code==422
 for i in range(3):c.post(path+'/final/bet',json={'participant':i,'amount':0})
 c.post(path+'/final/open');c.post(path+'/final/close')
 for i in range(3):c.post(path+'/final/judge',json={'participant':i,'decision':'ambiguous'})
 for i in range(3):g=c.post(path+'/final/reveal',json={'index':i}).json()
 assert g['show']['final']['winners']==[1,2]

def test_manual_judgement_with_steals_keeps_reference_private(stage):
 c,app,clock,ai,create,_=stage;path,pack=create({'steal':True})
 c.post(path+'/open',json={'cell':5})
 g=answer(c,path,'Свободный ответ',5).json();assert g['pending']['manual'] and 'correct_answer' not in g['pending']
 original_token=g['pending']['attempt_token']
 assert c.post(path+'/judge',json={'cell':5,'decision':'incorrect','attempt_token':original_token}).json()['pending']['steal']['stage']=='claim'
 c.post(path+'/steal/claim',json={'cell':5,'participant':1})
 g=answer(c,path,'Другой свободный ответ',5).json()
 assert g['pending']['manual'] and 'correct_answer' not in g['pending']
 assert c.post(path+'/judge',json={'cell':5,'decision':'correct','attempt_token':original_token}).status_code==409
 result=c.post(path+'/judge',json={'cell':5,'decision':'correct','attempt_token':g['pending']['attempt_token']}).json()
 assert [p['score'] for p in result['participants']]==[-100,100,0]
 assert result['results'][0]['delta']==100

def test_show_column_migration_preserves_legacy_game(stage):
 from sqlalchemy import text
 c,app,clock,ai,create,_=stage;path,pack=create()
 with app.state.engine.begin() as db:db.execute(text('ALTER TABLE trivia_games DROP COLUMN show_state'))
 app.state.initialize()
 g=c.get(path).json();assert g['show']['options']=={} and len(g['cells'])==40

def test_ai_outage_and_interrupted_final_use_local_fallback(stage,monkeypatch):
 c,app,clock,ai,create,_=stage;path,pack=create({'final':True,'host':'text','ai_comments':True},presentation=False)
 def unavailable(*args,**kwargs):raise RuntimeError('Simulated provider outage')
 monkeypatch.setattr(ai,'request',unavailable)
 eid=c.get(path).json()['show']['events'][-1]['id']
 g=c.post(path+'/host-comment',json={'event_id':eid}).json()
 g=c.get(path).json();assert not g['show']['comment_pending'] and g['show']['events'][-1]['text']
 complete_board(c,path,pack)
 for i in range(3):c.post(path+'/final/bet',json={'participant':i,'amount':0})
 g=c.post(path+'/final/open').json();assert g['show']['final']['source']=='local_fallback'
 from app.show_host import save
 with Session(app.state.engine) as db:
  row=db.get(TriviaGame,path.rsplit('/',1)[1]);s=state(row);s['phase']='final_preparing';s['final'].pop('clue');save(row,s);db.commit()
 app.state.initialize()
 assert c.get(path).json()['show']['phase']=='final_ready'
 assert c.post(path+'/final/open').json()['show']['final']['source']=='local_fallback'
