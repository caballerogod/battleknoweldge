import copy
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import create_app
from app.models import TriviaGame
from app.trivia import demo_pack
from app.trivia_party_demo import PARTY_TOPICS, party_demo
from app.quiz_ai import validate_pack
from app.trivia_media import format_plan, validate_mixed, image_url

NAMES=['Аня','Борис','Саша']

@pytest.fixture
def party(tmp_path):
    clock=[1000.]
    class Provider:
        configured=True
        def generate(self,topics):
            return party_demo(demo_pack())
        def grade(self,answer,clue):
            return dict(decision='correct',explanation='Смысл верен')
    app=create_app(f'sqlite:///{tmp_path/"party.db"}',clock=lambda:clock[0],quiz_provider=Provider())
    with TestClient(app) as c:
        p=c.post('/api/players',json={'nickname':'Хозяин партии'}).json()
        payload=dict(player_id=p['id'],request_id=str(uuid4()),topics=PARTY_TOPICS,participants=NAMES,demo=True)
        yield c,app,clock,payload


def test_party_40_turns_scores_privacy_and_replay_idempotent(party):
    c,app,clock,payload=party
    response=c.post('/api/trivia/games',json=payload)
    assert response.status_code==200,response.text
    g=response.json()
    assert g['total']==40 and len(g['cells'])==40 and [p['name'] for p in g['participants']]==NAMES
    assert all(set(cell)=={'cell','topic_index','price','played'} for cell in g['cells'])
    assert 'correct_answer' not in json.dumps(g)
    url='/api/trivia/games/'+g['id']
    scores=[0,0,0]
    with Session(app.state.engine) as db:
        clues=json.loads(db.get(TriviaGame,g['id']).pack)
    for i,q in enumerate(clues):
        opened=c.post(url+'/open',json={'cell':i}).json()
        assert opened['pending']['participant']==i%3
        assert opened['pending']['deadline']==1030
        assert 'answer' not in opened['pending'] and 'image_id' not in opened['pending']
        if q['kind']=='choice':
            assert opened['pending']['options']==q['options']
        out=c.post(url+'/answer',json={'cell':i,'answer':q['answer']}).json()
        scores[i%3]+=q['price']
        assert out['results'][-1]['participant']==i%3
        assert [p['score'] for p in out['participants']]==scores
        assert out['current_participant']==(i+1)%3
        assert c.post(url+'/answer',json={'cell':i,'answer':q['answer']}).json()['played']==i+1
    assert out['status']=='finished' and out['played']==40 and sum(scores)==12000
    assert c.post('/api/trivia/games',json={**payload,'participants':['Другой','Борис','Саша']}).status_code==409


def test_party_persistence_wrong_choice_timeout_and_bounds(party):
    c,app,clock,payload=party
    g=c.post('/api/trivia/games',json=payload).json()
    url='/api/trivia/games/'+g['id']
    with Session(app.state.engine) as db:clues=json.loads(db.get(TriviaGame,g['id']).pack)
    cell=next(i for i,q in enumerate(clues) if q['kind']=='choice')
    assert c.post(url+'/open',json={'cell':40}).status_code==422
    before=c.post(url+'/open',json={'cell':cell}).json()
    assert c.post(url+'/answer',json={'cell':cell,'answer':'не из списка'}).status_code==422
    app.state.initialize()
    stored=c.get(url).json()
    assert stored['pending']==before['pending'] and stored['participants']==before['participants']
    wrong=next(o for o in clues[cell]['options'] if o!=clues[cell]['answer'])
    result=c.post(url+'/answer',json={'cell':cell,'answer':wrong}).json()
    assert result['participants'][0]['score']==-clues[cell]['price']
    nextcell=next(i for i in range(40) if i!=cell)
    c.post(url+'/open',json={'cell':nextcell})
    clock[0]=1030
    timeout=c.post(url+'/answer',json={'cell':nextcell,'answer':clues[nextcell]['answer']}).json()
    assert timeout['results'][-1]['decision']=='timeout' and timeout['participants'][1]['score']==0
    assert timeout['current_participant']==2


@pytest.mark.parametrize('names,topics',[
    (['Один','Два'],PARTY_TOPICS),(['А','а','Б'],PARTY_TOPICS),(['А','','Б'],PARTY_TOPICS),
    (NAMES,PARTY_TOPICS[:5]),([],PARTY_TOPICS), (NAMES,[*PARTY_TOPICS[:7],PARTY_TOPICS[0]])])
def test_party_requires_three_names_and_eight_distinct_topics(party,names,topics):
    c,_,_,payload=party
    assert c.post('/api/trivia/games',json={**payload,'participants':names,'topics':topics}).status_code==422


def test_mixed_plan_and_media_validation():
    import random
    first=format_plan(PARTY_TOPICS,random.Random(1))
    assert first!=format_plan(PARTY_TOPICS,random.Random(2))
    assert all(p['price']<=300 for p in first if p['kind']=='image')
    assert len(first)==40 and {p['kind'] for p in first}=={'open','choice','riddle','image','audio','video'}
    for _ in range(20):
        clues=validate_pack({'clues':party_demo(demo_pack())},8)
        assert len(validate_mixed(clues))==40
    assert image_url('https://evil') is None
    bad=copy.deepcopy(clues)
    image=next(q for q in bad if q['kind']=='image')
    image['image_id']='../../secret'
    with pytest.raises(ValueError):validate_mixed(bad)
    bad=copy.deepcopy(clues)
    choice=next(q for q in bad if q['kind']=='choice')
    choice['options']=['один']*4
    with pytest.raises(ValueError):validate_mixed(bad)


def test_generated_party_keeps_formats(party):
    c,_,_,payload=party
    g=c.post('/api/trivia/games',json={**payload,'demo':False}).json()
    ready=c.get('/api/trivia/games/'+g['id']).json()
    assert ready['status']=='ready' and ready['total']==40

def test_choice_alias_cannot_credit_a_wrong_option(party):
    c,app,_,payload=party
    g=c.post('/api/trivia/games',json=payload).json()
    with Session(app.state.engine) as db:
        record=db.get(TriviaGame,g['id'])
        clues=json.loads(record.pack)
        cell=next(i for i,q in enumerate(clues) if q['kind']=='choice')
        wrong=next(o for o in clues[cell]['options'] if o!=clues[cell]['answer'])
        clues[cell]['aliases'].append(wrong)
        record.pack=json.dumps(clues,ensure_ascii=False)
        db.commit()
    url='/api/trivia/games/'+g['id']
    c.post(url+'/open',json={'cell':cell})
    result=c.post(url+'/answer',json={'cell':cell,'answer':wrong}).json()
    assert result['results'][-1]['decision']=='incorrect'
    assert result['participants'][0]['score']==-clues[cell]['price']
