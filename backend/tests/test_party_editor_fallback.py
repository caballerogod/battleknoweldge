import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import create_app
from app.models import TriviaGame
from app.quiz_ai import ReviewedClues, OpenAIQuiz
from app.trivia import demo_pack
from app.trivia_party_demo import PARTY_TOPICS, party_demo

@pytest.fixture
def party(tmp_path):
    class Provider:
        configured=True
        def generate(self,topics):
            return ReviewedClues(party_demo(demo_pack()),[dict(topic_index=0,price=100,reason='Check this reference')])
        def grade(self,*args):
            raise AssertionError('Flagged questions must never spend API money on grading')
    app=create_app(f'sqlite:///{tmp_path/"party.db"}',clock=lambda:1000,quiz_provider=Provider())
    with TestClient(app) as c:
        player=c.post('/api/players',json={'nickname':'Party QA'}).json()
        payload=dict(player_id=player['id'],request_id=str(uuid4()),topics=PARTY_TOPICS,participants=['А','Б','В'])
        g=c.post('/api/trivia/games',json=payload).json()
        yield c,app,'/api/trivia/games/'+g['id'],g['id']

def test_flagged_answer_is_private_until_locked_and_host_can_remove(party):
    c,app,url,sid=party
    g=c.get(url).json()
    assert g['status']=='ready' and g['host_review_count']==1
    with Session(app.state.engine) as db:answer=json.loads(db.get(TriviaGame,sid).pack)[0]['answer']
    g=c.post(url+'/open',json={'cell':0}).json()
    assert g['pending']['host_review'] and g['pending']['deadline']==1030
    assert 'correct_answer' not in g['pending'] and 'review_note' not in g['pending']
    assert c.post(url+'/judge',json={'cell':0,'decision':'correct'}).status_code==409
    g=c.post(url+'/answer',json={'cell':0,'answer':answer}).json()
    assert g['pending']['manual'] and g['played']==0
    assert g['pending']['correct_answer']==answer and g['pending']['review_note']=='Check this reference'
    assert c.post(url+'/answer',json={'cell':0,'answer':'changed'}).json()['pending']['submitted']==answer
    g=c.post(url+'/judge',json={'cell':0,'decision':'ambiguous'}).json()
    assert g['results'][0]['delta']==0 and g['current_participant']==1 and g['usage']['requests']==0
    assert c.post(url+'/judge',json={'cell':1,'decision':'correct'}).status_code==409

def test_failed_complete_draft_requires_explicit_recovery_and_no_ai(party):
    c,app,url,sid=party
    assert c.post(url+'/use-draft').status_code==409
    with Session(app.state.engine) as db:
        g=db.get(TriviaGame,sid);g.status='failed';g.error='Old editorial rejection';db.commit()
    assert c.get(url).json()['recoverable']
    g=c.post(url+'/use-draft').json()
    assert g['status']=='ready' and g['host_review_count']==40 and not g['error'] and g['usage']['requests']==0
    assert c.post(url+'/use-draft').status_code==409
    with Session(app.state.engine) as db:
        g=db.get(TriviaGame,sid);g.status='failed';g.pack='[]';db.commit()
    assert not c.get(url).json()['recoverable']
    assert c.post(url+'/use-draft').status_code==409

def test_review_outage_keeps_valid_board_for_host(monkeypatch):
    clues=party_demo(demo_pack())
    def unavailable(*args,**kwargs):raise RuntimeError('review outage')
    monkeypatch.setattr(OpenAIQuiz,'request',unavailable)
    result=OpenAIQuiz().edit_mixed(PARTY_TOPICS,clues,{'plan':[{k:q[k] for k in ('topic_index','price','kind','image_id')} for q in clues]},'party rules')
    assert result==clues and len(result.editorial_notes)==40
