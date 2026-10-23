import json
import random
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adaptive import CATEGORIES, Knowledge, category_weights, choose_question, difficulty_for, level_for, xp_for
from app.main import create_app
from app.models import Achievement, Answer, GameSession, Player, PlayerAchievement, Question
from app.questions import question_rows


@pytest.fixture
def battle(tmp_path):
    app = create_app(f'sqlite:///{tmp_path / "test.db"}', random.Random(42))
    with TestClient(app) as client:
        yield client, app


def start(client):
    p = client.post('/api/players', json={'nickname':'Тест'}).json()
    g = client.post('/api/sessions', json={'player_id':p['id']}).json()
    return p, g


def correct_for(app, qid):
    with Session(app.state.engine) as db:
        return db.get(Question, qid).correct


def respond(client, app, sid, correct=True):
    q = client.post(f'/api/sessions/{sid}/next', json={}).json()
    c = correct_for(app, q['id'])
    response = client.post(f'/api/sessions/{sid}/answers', json={'question_id':q['id'],'selected':c if correct else (c+1)%4})
    assert response.status_code == 200, response.text
    return q, response.json()


def test_bank_distribution_and_integrity():
    rows = question_rows()
    assert len(rows) == 90
    assert len({q['text'].strip().casefold() for q in rows}) == 90
    assert set(Counter((q['category'], q['difficulty']) for q in rows).values()) == {6}
    assert len(Counter((q['category'], q['difficulty']) for q in rows)) == 15
    for q in rows:
        options = json.loads(q['options'])
        assert len(set(options)) == 4 and 0 <= q['correct'] < 4 and len(q['explanation']) > 20


def test_database_creation_and_idempotent_seed(battle):
    client, app = battle
    app.state.initialize()
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Question)) == 90
        assert db.scalar(select(func.count()).select_from(Achievement)) == 6
    assert client.get('/api/health').json() == {'status':'ok'}


def test_player_validation_and_persistence(battle):
    client, _ = battle
    p, g = start(client)
    assert client.post('/api/players',json={'nickname':'  Тест  '}).json()['id'] == p['id']
    assert client.post('/api/players',json={'nickname':'  '}).status_code == 422
    assert client.post('/api/players',json={'nickname':'x'*41}).status_code == 422
    assert client.get(f'/api/players/{p["id"]}').json()['level'] == 1
    assert client.post('/api/sessions',json={'player_id':p['id']}).json()['id'] == g['id']
    assert client.get('/api/players/999').status_code == 404


def test_pending_question_survives_refresh_and_no_solution_leak(battle):
    client, _ = battle
    _, g = start(client)
    q = client.post(f'/api/sessions/{g["id"]}/next',json={}).json()
    repeated = client.post(f'/api/sessions/{g["id"]}/next',json={}).json()
    assert {k:v for k,v in repeated.items() if k!='server_time'} == {k:v for k,v in q.items() if k!='server_time'}
    assert 'correct' not in q and 'explanation' not in q
    state = client.get(f'/api/sessions/{g["id"]}').json()
    assert state['pending_id'] == q['id'] and state['last_answer'] is None


def test_correct_wrong_xp_and_first_achievement(battle):
    client, app = battle
    p, g = start(client)
    _, first = respond(client,app,g['id'])
    assert first['answer']['is_correct'] and first['answer']['xp'] == 20
    assert first['player']['xp'] == 20
    assert first['new_achievements'] == ['first']
    _, wrong = respond(client,app,g['id'],False)
    assert not wrong['answer']['is_correct'] and wrong['answer']['xp'] == 0
    assert wrong['session']['streak'] == 0 and wrong['player']['xp'] == 20
    assert wrong['session']['correct'] == 1 and wrong['session']['wrong'] == 1


def test_no_double_credit_and_foreign_question(battle):
    client, app = battle
    p, g = start(client)
    assert client.post(f'/api/sessions/{g["id"]}/answers',json={'question_id':1,'selected':0}).status_code == 409
    q, result = respond(client,app,g['id'])
    duplicate = client.post(f'/api/sessions/{g["id"]}/answers',json={'question_id':q['id'],'selected':correct_for(app,q['id'])})
    assert duplicate.status_code == 409
    assert client.get(f'/api/players/{p["id"]}').json()['xp'] == result['player']['xp']
    assert client.post(f'/api/sessions/{g["id"]}/answers',json={'question_id':q['id'],'selected':4}).status_code == 422


def test_concurrent_answer_is_atomic(battle):
    client, app = battle
    p,g = start(client)
    q = client.post(f'/api/sessions/{g["id"]}/next',json={}).json()
    def send(_):
        return client.post(f'/api/sessions/{g["id"]}/answers',json={'question_id':q['id'],'selected':correct_for(app,q['id'])}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(send,range(2))) == [200,409]
    assert client.get(f'/api/players/{p["id"]}').json()['xp'] == 20


def test_full_round_no_repeats_streak_levels_and_achievements(battle):
    client, app = battle
    p,g = start(client)
    seen = set()
    xp = 0
    for i in range(10):
        q, result = respond(client,app,g['id'])
        assert q['id'] not in seen
        seen.add(q['id'])
        expected = {'easy':10,'medium':20,'hard':30}[q['difficulty']] + (30 if (i+1)%5==0 else 0)
        assert result['answer']['xp'] == expected
        xp += expected
    assert client.post(f'/api/sessions/{g["id"]}/next',json={}).status_code == 409
    finish = client.post(f'/api/sessions/{g["id"]}/finish',json={}).json()
    assert finish['finished'] and finish['accuracy'] == 100 and finish['xp'] == xp
    assert finish['current_level'] == level_for(xp)
    assert set(finish['achievements']) == {'Первый шаг','Серия побед','Без ошибок'}
    assert client.post(f'/api/sessions/{g["id"]}/finish',json={}).json() == finish
    assert client.post(f'/api/sessions/{g["id"]}/next',json={}).status_code == 409
    stats = client.get(f'/api/players/{p["id"]}/stats').json()
    assert stats['games'] == 1 and len(stats['history']) == 10
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(PlayerAchievement)) == 3
        assert db.scalar(select(func.count()).select_from(Answer)) == 10


def test_partial_round_does_not_award_perfect(battle):
    client,app = battle
    _,g = start(client)
    respond(client,app,g['id'])
    result = client.post(f'/api/sessions/{g["id"]}/finish',json={}).json()
    assert 'Без ошибок' not in result['achievements']


def test_new_session_does_not_reissue_one_time_award(battle):
    client,app = battle
    p,g = start(client)
    respond(client,app,g['id'])
    client.post(f'/api/sessions/{g["id"]}/finish',json={})
    g2 = client.post('/api/sessions',json={'player_id':p['id']}).json()
    assert g2['id'] != g['id']
    _,result = respond(client,app,g2['id'])
    assert 'first' not in result['new_achievements']
    assert 'Первый шаг' not in result['session']['achievements']


def test_restart_keeps_answers_and_pending(battle):
    client,app = battle
    p,g = start(client)
    respond(client,app,g['id'])
    q = client.post(f'/api/sessions/{g["id"]}/next',json={}).json()
    restarted = create_app(str(app.state.engine.url))
    with TestClient(restarted) as c2:
        assert c2.get(f'/api/players/{p["id"]}').json()['xp'] == 20
        assert c2.post(f'/api/sessions/{g["id"]}/next',json={}).json()['id'] == q['id']


def test_adaptation_smoothing_and_difficulty():
    assert Knowledge(1,0).mastery == pytest.approx(1/3)
    assert difficulty_for(Knowledge(1,0)) == 'medium'
    assert difficulty_for(Knowledge(8,1)) == 'easy'
    assert difficulty_for(Knowledge(8,7)) == 'hard'
    assert difficulty_for(Knowledge(8,4)) == 'medium'
    weights=category_weights({'Математика':Knowledge(20,2),'История':Knowledge(20,18)})
    assert weights['Математика'] > weights['История']
    assert sum(weights.values()) == pytest.approx(1)
    assert min(weights.values()) >= .06


def test_controlled_category_selection_and_difficulty_fallback():
    questions=[SimpleNamespace(id=i,category=c,difficulty=d) for i,(c,d) in enumerate(( (c,d) for c in CATEGORIES for d in ['easy','medium','hard']))]
    stats={'Математика':Knowledge(20,1),'История':Knowledge(20,19)}
    rng=random.Random(99)
    counts=Counter(choose_question(questions,set(),stats,rng).category for _ in range(2000))
    assert counts['Математика'] > counts['История']*2
    math=[q for q in questions if q.category=='Математика']
    assert choose_question(math,set(),stats,random.Random(1)).difficulty == 'easy'
    assert choose_question(math,{math[0].id},stats,random.Random(1)).difficulty == 'medium'
    assert choose_question(math,{q.id for q in math},stats) is None


def test_xp_rules():
    assert xp_for('easy',True,1)==10
    assert xp_for('medium',True,5)==50
    assert xp_for('hard',True,10)==60
    assert xp_for('hard',False,0)==0


def test_category_and_scholar_achievements_require_enough_answers(battle):
    client, app = battle
    p,g = start(client)
    # Historical fixtures: category awards must be evaluated over all player answers.
    with Session(app.state.engine) as db:
        previous = GameSession(id='history',player_id=p['id'],finished_at='2026-01-01')
        db.add(previous)
        db.flush()
        for category in ['Программирование','Математика','История']:
            for q in db.scalars(select(Question).where(Question.category==category).limit(10)):
                db.add(Answer(session_id='history',player_id=p['id'],question_id=q.id,selected=q.correct,is_correct=True,xp=0))
        db.commit()
    _,result=respond(client,app,g['id'])
    assert {'math','code','scholar'} <= set(result['new_achievements'])
    earned=client.get(f'/api/players/{p["id"]}/achievements').json()
    assert all(a['earned_at'] for a in earned if a['id'] in ['math','code','scholar'])


def test_unassigned_question_from_another_session_rejected(battle):
    client,app=battle
    _,g=start(client)
    other=client.post('/api/players',json={'nickname':'Другой'}).json()
    foreign=client.post('/api/sessions',json={'player_id':other['id']}).json()
    q=client.post(f'/api/sessions/{foreign["id"]}/next',json={}).json()
    assert client.post(f'/api/sessions/{g["id"]}/answers',json={'question_id':q['id'],'selected':0}).status_code==409


def test_client_cannot_set_xp(battle):
    client,app=battle
    p,g=start(client)
    q=client.post(f'/api/sessions/{g["id"]}/next',json={}).json()
    result=client.post(f'/api/sessions/{g["id"]}/answers',json={'question_id':q['id'],'selected':correct_for(app,q['id']),'xp':99999}).json()
    assert result['player']['xp']==20
