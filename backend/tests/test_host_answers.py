import json
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import create_app
from app.models import TriviaGame
from app.trivia_party_demo import PARTY_TOPICS

def test_host_sheet_preserves_all_answers_without_leaking_into_player_view(tmp_path):
    class NoAI:
        configured=False
        def generate(self,*args):raise AssertionError('No paid calls')
        grade=generate
    app=create_app(f'sqlite:///{tmp_path/"host.db"}',quiz_provider=NoAI())
    with TestClient(app) as c:
        player=c.post('/api/players',json={'nickname':'Host QA'}).json()
        g=c.post('/api/trivia/games',json=dict(player_id=player['id'],request_id=str(uuid4()),topics=PARTY_TOPICS,participants=['А','Б','В'],demo=True)).json()
        url='/api/trivia/games/'+g['id']
        assert 'answer' not in g['cells'][0]
        response=c.get(url+'/host-sheet');assert response.status_code==200
        assert response.headers['cache-control']=='no-store'
        sheet=response.json();assert len(sheet['topics'])==8
        with Session(app.state.engine) as db:pack=json.loads(db.get(TriviaGame,g['id']).pack)
        questions=[q for t in sheet['topics'] for q in t['questions']]
        assert len(questions)==40
        for i,q in enumerate(questions):
            assert q['cell']==i and q['answer']==pack[i]['answer']
            assert q['explanation']==pack[i]['explanation'] and q['aliases']==pack[i]['aliases']
        opened=c.post(url+'/open',json={'cell':0}).json()
        assert 'correct_answer' not in opened['pending']
        assert c.get(url).json()['played']==0
        c.post(url+'/answer',json={'cell':0,'skip':True})
        c.post(url+'/finish')
        assert c.get(url+'/host-sheet').json()==sheet
        with Session(app.state.engine) as db:
            game=db.get(TriviaGame,g['id']);game.status='generating';db.commit()
        assert c.get(url+'/host-sheet').status_code==409
        assert c.get('/api/trivia/games/missing/host-sheet').status_code==404
