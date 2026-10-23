from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.trivia_party_demo import PARTY_TOPICS

def test_audience_pause_survives_restart_and_resume_preserves_remaining_time(tmp_path):
    url=f'sqlite:///{tmp_path/"audience.db"}'
    clock=[1000.]
    app=create_app(url,clock=lambda:clock[0])
    with TestClient(app) as c:
        p=c.post('/api/players',json={'nickname':'Audience QA'}).json()
        g=c.post('/api/trivia/games',json=dict(player_id=p['id'],request_id=str(uuid4()),topics=PARTY_TOPICS,participants=['А','Б','В'],demo=True)).json()
        path='/api/trivia/games/'+g['id']
        assert c.post(path+'/audience-help',json={'cell':0}).status_code==409
        opened=c.post(path+'/open',json={'cell':0}).json()['pending']
        assert opened['deadline']==1060 and opened['time_limit']==60
        clock[0]=1017.5
        paused=c.post(path+'/audience-help',json={'cell':0}).json()['pending']
        assert paused['paused'] and paused['remaining']==42.5
        clock[0]=2000
        assert c.post(path+'/audience-help',json={'cell':0}).json()['pending']['remaining']==42.5
        assert c.post(path+'/answer',json={'cell':0,'answer':'guess'}).status_code==409
        assert c.post(path+'/resume-answer',json={'cell':1}).status_code==409
    app=create_app(url,clock=lambda:clock[0])
    with TestClient(app) as c:
        assert c.get(path).json()['pending']['remaining']==42.5
        resumed=c.post(path+'/resume-answer',json={'cell':0}).json()['pending']
        assert not resumed['paused'] and resumed['deadline']==2042.5
        clock[0]=2010
        assert c.post(path+'/resume-answer',json={'cell':0}).json()['pending']['deadline']==2042.5
        clock[0]=2042.5
        expired=c.post(path+'/audience-help',json={'cell':0}).json()
        assert expired['results'][0]['decision']=='timeout' and expired['pending'] is None
        assert c.post(path+'/resume-answer',json={'cell':0}).status_code==409
        assert c.post(path+'/open',json={'cell':1}).json()['pending']['deadline']==2102.5
