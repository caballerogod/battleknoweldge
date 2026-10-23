import json
import random
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import create_app
from app.models import TriviaGame
from app import presentation_bank as bank

class NoAI:
    configured = False
    def generate(self, *args, **kwargs):
        raise AssertionError('Presentation must never call AI')
    grade = generate

@pytest.fixture
def stage(tmp_path):
    clock = [1000.]
    app = create_app(f'sqlite:///{tmp_path / "stage.db"}', clock=lambda: clock[0], quiz_provider=NoAI())
    with TestClient(app) as client:
        player = client.post('/api/players', json={'nickname':'Stage QA'}).json()
        payload = dict(player_id=player['id'], request_id=str(uuid4()), topics=list(bank.RAW)[:8], participants=['Аня','Борис','Саша'], presentation=True)
        yield client, app, clock, payload

def test_all_230_clues_and_random_boards():
    assert len(bank.catalog()) == 23
    questions=[]
    for topic in bank.RAW:
        for reserve in (False, True):
            clues=bank.rows(topic,reserve)
            assert len(clues)==5
            assert [q['price'] for q in clues]==[100,200,300,400,500]
            questions.extend(q['question'] for q in clues)
    assert len(set(questions))==230
    rng=random.Random(42)
    for _ in range(100):
        pack,meta=bank.presentation_pack(rng.sample(list(bank.RAW),8),rng.choice([True,False]))
        assert len(pack)==40 and not meta['fallback_topics']


def test_fallback_preserves_other_topics(monkeypatch):
    original=bank.rows
    topics=list(bank.RAW)[:8]
    def broken(topic,reserve=False):
        if topic==topics[0] and not reserve:
            raise ValueError('damaged primary bank')
        return original(topic,reserve)
    monkeypatch.setattr(bank,'rows',broken)
    pack,meta=bank.presentation_pack(topics)
    assert meta['fallback_topics']==topics[:1]
    assert pack[0]['question']==original(topics[0],True)[0]['question']
    assert pack[5]['question']==original(topics[1])[0]['question']


def test_catalog_creation_reserve_and_idempotency_without_key(stage):
    c,app,clock,payload=stage
    config=c.get('/api/trivia/config').json()
    assert not config['configured'] and len(config['presentation_topics'])==23
    assert all(set(t)=={'name','aliases'} for t in config['presentation_topics'])
    g=c.post('/api/trivia/games',json=payload).json()
    assert g['status']=='ready' and g['presentation'] and g['total']==40
    assert g['usage']['requests']==0
    assert c.post('/api/trivia/games',json=payload).json()['id']==g['id']
    assert c.post('/api/trivia/games',json={**payload,'reserve':True}).status_code==409
    other=c.post('/api/trivia/games',json={**payload,'request_id':str(uuid4()),'reserve':True}).json()
    with Session(app.state.engine) as db:
        primary=json.loads(db.get(TriviaGame,g['id']).pack)
        reserve=json.loads(db.get(TriviaGame,other['id']).pack)
    assert not {q['question'] for q in primary}&{q['question'] for q in reserve}
    assert c.post('/api/trivia/games',json={**payload,'request_id':str(uuid4()),'topics':['unknown',*payload['topics'][1:]]}).status_code==422


def test_complete_party_host_lock_scores_privacy_and_timeout(stage):
    c,app,clock,payload=stage
    g=c.post('/api/trivia/games',json=payload).json()
    url='/api/trivia/games/'+g['id']
    with Session(app.state.engine) as db:
        clues=json.loads(db.get(TriviaGame,g['id']).pack)
    scores=[0,0,0]
    for i,q in enumerate(clues):
        g=c.post(url+'/open',json={'cell':i}).json()
        assert g['pending']['deadline']==clock[0]+60
        assert 'correct_answer' not in g['pending']
        assert c.post(url+'/judge',json={'cell':i,'decision':'correct'}).status_code==409
        if i==39:
            clock[0]+=61
            g=c.post(url+'/answer',json={'cell':i,'answer':q['answer']}).json()
            assert g['results'][-1]['decision']=='timeout'
        elif q['kind']=='choice' or i%2==0:
            g=c.post(url+'/answer',json={'cell':i,'answer':q['answer']}).json()
            scores[i%3]+=q['price']
        else:
            g=c.post(url+'/answer',json={'cell':i,'answer':'Свободная формулировка игрока'}).json()
            assert g['pending']['manual'] and g['pending']['correct_answer']==q['answer']
            assert c.get(url).json()['pending']['manual']
            locked=c.post(url+'/answer',json={'cell':i,'answer':'Подменённый ответ'}).json()
            assert locked['pending']['submitted']=='Свободная формулировка игрока'
            clock[0]+=61
            decision='incorrect' if i%3==0 else 'correct'
            g=c.post(url+'/judge',json={'cell':i,'decision':decision}).json()
            scores[i%3]+=q['price']*(-1 if decision=='incorrect' else 1)
            assert c.post(url+'/judge',json={'cell':i,'decision':decision}).json()['played']==i+1
        assert g['played']==i+1
        assert [p['score'] for p in g['participants']]==scores
    assert g['status']=='finished' and g['usage']['requests']==0

def test_manual_answer_survives_restart_and_old_database_migrates(tmp_path):
    from sqlalchemy import text
    path=f'sqlite:///{tmp_path / "upgrade.db"}'
    app=create_app(path,quiz_provider=NoAI())
    with TestClient(app) as c:
        player=c.post('/api/players',json={'nickname':'Persist'}).json()
        g=c.post('/api/trivia/games',json=dict(player_id=player['id'],request_id=str(uuid4()),topics=list(bank.RAW)[:8],participants=['А','Б','В'],presentation=True)).json()
        url='/api/trivia/games/'+g['id']
        c.post(url+'/open',json={'cell':0})
        answer=c.post(url+'/answer',json={'cell':0,'answer':'Ответ своими словами'}).json()
        assert answer['pending']['manual']
    app=create_app(path,quiz_provider=NoAI())
    with TestClient(app) as c:
        assert c.get(url).json()['pending']['submitted']=='Ответ своими словами'
        assert c.post(url+'/judge',json={'cell':0,'decision':'ambiguous'}).json()['played']==1
    # Simulate the schema used by the previous app release.
    with app.state.engine.begin() as connection:
        connection.execute(text('ALTER TABLE trivia_games DROP COLUMN presentation_meta'))
    app=create_app(path,quiz_provider=NoAI())
    with TestClient(app) as c:
        assert c.get(url).status_code==200
        assert c.get(url).json()['participants'][0]['name']=='А'

@pytest.mark.parametrize('reserve',[False,True])
def test_expanded_presentation_complete_party_never_uses_ai(stage,reserve):
    from app.trivia_media import SPECIAL_TOPICS
    c,app,clock,payload=stage
    topics=[*SPECIAL_TOPICS,'Музыка','Космос','Наука','Математика','География']
    response=c.post('/api/trivia/games',json={**payload,'topics':topics,'reserve':reserve})
    assert response.status_code==200,response.text
    g=response.json();url='/api/trivia/games/'+g['id']
    assert g['status']=='ready' and g['usage']['requests']==0
    assert g['presentation_info']['bank_set']==('reserve' if reserve else 'main')
    with Session(app.state.engine) as db:clues=json.loads(db.get(TriviaGame,g['id']).pack)
    scores=[0,0,0]
    for i,q in enumerate(clues):
        opened=c.post(url+'/open',json={'cell':i}).json()
        pending=opened['pending']
        assert pending['deadline']==clock[0]+60
        assert pending['participant']==i%3 and 'correct_answer' not in pending
        if pending['media']:
            assert not {'reference','source','credit'}&set(pending['media'])
        if q['kind']=='yesno':assert pending['options']==['Да','Нет']
        if i==5:
            g=c.post(url+'/answer',json={'cell':i,'answer':'Три ответа своими словами'}).json()
            assert g['pending']['manual']
            assert g['pending']['correct_answer']==q['answer']
            g=c.post(url+'/judge',json={'cell':i,'decision':'correct'}).json()
            scores[i%3]+=q['price']
        elif i==10:
            wrong='Да' if q['answer']=='Нет' else 'Нет'
            g=c.post(url+'/answer',json={'cell':i,'answer':wrong}).json()
            scores[i%3]-=q['price']
        elif i==39:
            clock[0]+=61
            g=c.post(url+'/answer',json={'cell':i,'answer':q['answer']}).json()
            assert g['results'][-1]['decision']=='timeout'
        else:
            g=c.post(url+'/answer',json={'cell':i,'answer':q['answer']}).json()
            scores[i%3]+=q['price']
        assert g['played']==i+1 and [p['score'] for p in g['participants']]==scores
        if i<5:assert g['results'][-1]['media']['mask']=='none'
    assert g['status']=='finished' and g['usage']['requests']==0


def test_new_catalog_topics_and_independent_reserve_stills():
    from app.trivia_media import SPECIAL_TOPICS, MEDIA_CATALOG
    from pathlib import Path
    assert [t['name'] for t in bank.catalog()[:3]]==SPECIAL_TOPICS
    primary=bank.rows(SPECIAL_TOPICS[0]);reserve=bank.rows(SPECIAL_TOPICS[0],True)
    ids=lambda clues:{q['image_id'] for q in clues}
    assert not ids(primary)&ids(reserve)
    assert {q['answer'] for q in primary}=={q['answer'] for q in reserve}
    root=Path(__file__).resolve().parents[2]/'frontend/public'
    for p,r in zip(primary,reserve):
        assert (root/MEDIA_CATALOG[p['image_id']]['url'].lstrip('/')).read_bytes()!=(root/MEDIA_CATALOG[r['image_id']]['url'].lstrip('/')).read_bytes()
    for is_reserve in (False,True):
        all_clues=[q for t in bank.RAW for q in bank.rows(t,is_reserve)]
        media=[q['image_id'] for q in all_clues if q['image_id']]
        assert len(media)==len(set(media))
        assert {'image','audio','video','linked','yesno'}<={q['kind'] for q in all_clues}
        for q in bank.rows('Да или Нет',is_reserve):assert q['options']==['Да','Нет']
