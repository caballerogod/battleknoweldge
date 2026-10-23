import random
import sqlite3
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import create_app
from test_battle import correct_for, start


def test_deadline_is_30_seconds_and_does_not_reset(tmp_path):
    clock=[1000.]
    app=create_app(f'sqlite:///{tmp_path / "timer.db"}',random.Random(1),lambda:clock[0])
    with TestClient(app) as c:
        _,g=start(c)
        q=c.post(f'/api/sessions/{g["id"]}/next',json={}).json()
        assert q['deadline_at']==1030 and q['time_limit']==30
        clock[0]=1024
        again=c.post(f'/api/sessions/{g["id"]}/next',json={}).json()
        assert again['id']==q['id'] and again['deadline_at']==1030 and again['server_time']==1024


def test_timeout_records_missed_answer_without_xp_and_rejects_duplicate(tmp_path):
    clock=[1000.]
    app=create_app(f'sqlite:///{tmp_path / "timer.db"}',clock=lambda:clock[0])
    with TestClient(app) as c:
        p,g=start(c)
        q=c.post(f'/api/sessions/{g["id"]}/next',json={}).json()
        url=f'/api/sessions/{g["id"]}/answers'
        assert c.post(url,json={'question_id':q['id'],'selected':None}).status_code==409
        clock[0]=1030
        result=c.post(url,json={'question_id':q['id'],'selected':None}).json()
        assert result['answer']['timed_out'] and result['answer']['selected'] is None
        assert result['answer']['xp']==0 and result['player']['xp']==0 and result['session']['wrong']==1
        assert c.post(url,json={'question_id':q['id'],'selected':None}).status_code==409
        next_q=c.post(f'/api/sessions/{g["id"]}/next',json={}).json()
        assert next_q['deadline_at']==1060
        assert c.get(f'/api/players/{p["id"]}/stats').json()['history'][0]['timed_out']


def test_correct_but_late_answer_is_timeout(tmp_path):
    clock=[1000.]
    app=create_app(f'sqlite:///{tmp_path / "timer.db"}',clock=lambda:clock[0])
    with TestClient(app) as c:
        _,g=start(c)
        q=c.post(f'/api/sessions/{g["id"]}/next',json={}).json()
        clock[0]=1030.001
        result=c.post(f'/api/sessions/{g["id"]}/answers',json={'question_id':q['id'],'selected':correct_for(app,q['id'])}).json()
        assert result['answer']['timed_out'] and not result['answer']['is_correct'] and result['answer']['xp']==0


def test_timely_correct_answer_is_not_timeout(tmp_path):
    clock=[1000.]
    app=create_app(f'sqlite:///{tmp_path / "timer.db"}',clock=lambda:clock[0])
    with TestClient(app) as c:
        _,g=start(c)
        q=c.post(f'/api/sessions/{g["id"]}/next',json={}).json()
        clock[0]=1029.999
        result=c.post(f'/api/sessions/{g["id"]}/answers',json={'question_id':q['id'],'selected':correct_for(app,q['id'])}).json()
        assert not result['answer']['timed_out'] and result['answer']['is_correct'] and result['answer']['xp']==20


def test_finish_after_deadline_records_timeout(tmp_path):
    clock=[1000.]
    app=create_app(f'sqlite:///{tmp_path / "timer.db"}',clock=lambda:clock[0])
    with TestClient(app) as c:
        _,g=start(c)
        c.post(f'/api/sessions/{g["id"]}/next',json={})
        clock[0]=1040
        result=c.post(f'/api/sessions/{g["id"]}/finish',json={}).json()
        assert result['wrong']==1 and result['last_answer']['timed_out'] and result['xp']==0


def test_existing_database_migrates_without_losing_players(tmp_path):
    path=tmp_path/'legacy.db'
    app=create_app(f'sqlite:///{path}')
    with TestClient(app) as c:
        p,_=start(c)
    connection=sqlite3.connect(path)
    connection.execute('ALTER TABLE game_sessions DROP COLUMN deadline_at')
    connection.commit();connection.close()
    upgraded=create_app(f'sqlite:///{path}')
    with TestClient(upgraded) as c:
        assert c.get(f'/api/players/{p["id"]}').json()['nickname']==p['nickname']
        upgraded.state.initialize()
        with upgraded.state.engine.connect() as connection:
            assert 'deadline_at' in [row[1] for row in connection.execute(text('PRAGMA table_info(game_sessions)'))]


def test_deadline_survives_backend_restart(tmp_path):
    url=f'sqlite:///{tmp_path / "restart.db"}'
    clock=[1000.]
    app=create_app(url,clock=lambda:clock[0])
    with TestClient(app) as c:
        _,g=start(c)
        q=c.post(f'/api/sessions/{g["id"]}/next',json={}).json()
    clock[0]=1025
    with TestClient(create_app(url,clock=lambda:clock[0])) as c:
        resumed=c.post(f'/api/sessions/{g["id"]}/next',json={}).json()
        assert resumed['id']==q['id'] and resumed['deadline_at']==1030 and resumed['server_time']==1025
