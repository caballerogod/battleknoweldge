import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import create_app
from app.models import TriviaGame
from app.quiz_ai import exact_answer, normalize, validate_pack, OpenAIQuiz
from app.trivia import DEMO_TOPICS, demo_pack


class TestProvider:
    __test__ = False
    configured = True
    calls = 0
    decision = 'correct'
    fail = False
    checked = []

    def generate(self, topics):
        self.calls += 1
        return demo_pack()

    def grade(self, answer, clue):
        self.checked = [*self.checked, answer]
        if self.fail:
            raise RuntimeError('offline')
        return dict(decision=self.decision, explanation='Тестовая проверка адаптера')


@pytest.fixture
def trivia(tmp_path):
    clock, provider = [1000.], TestProvider()
    app = create_app(f'sqlite:///{tmp_path / "trivia.db"}', clock=lambda: clock[0], quiz_provider=provider)
    with TestClient(app) as c:
        player = c.post('/api/players', json={'nickname': 'Своя игра QA'}).json()
        yield c, app, clock, provider, player


def create(c, player, demo=True, **extra):
    payload = dict(player_id=player['id'], topics=DEMO_TOPICS, request_id=str(uuid4()), demo=demo)
    payload.update(extra)
    return c.post('/api/trivia/games', json=payload)


def test_board_is_complete_and_answers_never_leak(trivia):
    c, _, _, _, player = trivia
    game = create(c, player).json()
    assert game['demo'] and len(game['cells']) == 25
    assert all(set(cell) == {'cell', 'topic_index', 'price', 'played'} for cell in game['cells'])
    assert 'answer' not in json.dumps(game)
    assert [cell['price'] for cell in game['cells'][:5]] == [100, 200, 300, 400, 500]
    opened = c.post(f'/api/trivia/games/{game["id"]}/open', json={'cell': 0}).json()
    assert opened['pending']['question'] == demo_pack()[0]['question']
    assert 'correct_answer' not in json.dumps(opened)


def test_no_key_does_not_silently_generate_demo(trivia):
    c, _, _, provider, player = trivia
    provider.configured = False
    assert c.get('/api/trivia/config').json()['configured'] is False
    assert create(c, player, demo=False).status_code == 503
    assert provider.calls == 0
    assert create(c, player, demo=True).status_code == 200


def test_topics_must_be_five_unique_and_demo_topics_are_fixed(trivia):
    c, _, _, _, player = trivia
    assert create(c, player, topics=['Наука']*5).status_code == 422
    assert create(c, player, topics=DEMO_TOPICS[:4]).status_code == 422
    assert create(c, player, topics=['Космос', *DEMO_TOPICS[1:]]).status_code == 422


def test_generation_idempotent_and_real_mode_separate(trivia):
    c, _, _, provider, player = trivia
    rid = str(uuid4())
    game = create(c, player, False, request_id=rid).json()
    same = create(c, player, False, request_id=rid).json()
    ready = c.get(f'/api/trivia/games/{game["id"]}').json()
    assert same['id'] == game['id'] and provider.calls == 1
    assert ready['status'] == 'ready' and not ready['demo']
    assert create(c, player, False, request_id=rid, topics=['Космос', *DEMO_TOPICS[1:]]).status_code == 409


def test_refresh_preserves_deadline_and_cannot_open_two_cells(trivia):
    c, _, clock, _, player = trivia
    game = create(c, player).json()
    url = f'/api/trivia/games/{game["id"]}'
    assert c.post(url+'/answer', json={'cell': 0, 'answer': 'int'}).status_code == 409
    first = c.post(url+'/open', json={'cell': 0}).json()
    clock[0] += 12
    assert c.get(url).json()['pending']['deadline'] == first['pending']['deadline'] == 1060
    assert c.post(url+'/open', json={'cell': 0}).json()['pending']['deadline'] == 1060
    assert c.post(url+'/open', json={'cell': 1}).status_code == 409


def test_expired_answer_zero_points_even_if_correct(trivia):
    c, _, clock, _, player = trivia
    game = create(c, player).json()
    url = f'/api/trivia/games/{game["id"]}'
    c.post(url+'/open', json={'cell': 0})
    clock[0] = 1060
    result = c.post(url+'/answer', json={'cell': 0, 'answer': 'int'}).json()
    assert result['results'][0]['decision'] == 'timeout' and result['score'] == 0


def test_free_answer_score_idempotence_skip_and_used_cell(trivia):
    c, _, _, _, player = trivia
    game = create(c, player).json()
    url = f'/api/trivia/games/{game["id"]}'
    c.post(url+'/open', json={'cell': 0})
    result = c.post(url+'/answer', json={'cell': 0, 'answer': 'Это INT.'}).json()
    assert result['score'] == 100 and result['played'] == 1
    assert c.post(url+'/answer', json={'cell': 0, 'answer': 'другой'}).json()['score'] == 100
    assert c.post(url+'/open', json={'cell': 0}).status_code == 409
    c.post(url+'/open', json={'cell': 1})
    assert c.post(url+'/answer', json={'cell': 1, 'answer': 'неправильно'}).json()['score'] == -100
    c.post(url+'/open', json={'cell': 2})
    skipped = c.post(url+'/answer', json={'cell': 2, 'skip': True}).json()
    assert skipped['score'] == -100 and skipped['results'][-1]['decision'] == 'skip'


def test_semantic_grading_and_ambiguity(trivia):
    c, _, _, provider, player = trivia
    game = create(c, player, False).json()
    url = f'/api/trivia/games/{game["id"]}'
    c.post(url+'/open', json={'cell': 0})
    c.post(url+'/answer', json={'cell': 0, 'answer': 'тип целого числа'})
    assert c.get(url).json()['score'] == 100
    provider.decision = 'ambiguous'
    c.post(url+'/open', json={'cell': 1})
    c.post(url+'/answer', json={'cell': 1, 'answer': 'неоднозначный ответ'})
    result = c.get(url).json()
    assert result['score'] == 100 and result['results'][-1]['decision'] == 'ambiguous'


def test_failed_grade_keeps_answer_and_allows_retry_after_deadline(trivia):
    c, _, clock, provider, player = trivia
    game = create(c, player, False).json()
    url = f'/api/trivia/games/{game["id"]}'
    c.post(url+'/open', json={'cell': 0})
    provider.fail = True
    c.post(url+'/answer', json={'cell': 0, 'answer': 'исходный ответ'})
    waiting = c.get(url).json()
    assert waiting['pending']['submitted'] == 'исходный ответ' and waiting['pending']['grade_error']
    assert waiting['score'] == 0 and waiting['played'] == 0
    clock[0] = 1200
    provider.fail = False
    c.post(url+'/answer', json={'cell': 0, 'answer': 'подменённый ответ'})
    assert provider.checked[-1] == 'исходный ответ'
    assert c.get(url).json()['results'][-1]['decision'] == 'correct'


def test_complete_25_cells_and_finish_idempotent(trivia):
    c, _, _, _, player = trivia
    game = create(c, player).json()
    url = f'/api/trivia/games/{game["id"]}'
    for i, clue in enumerate(demo_pack()):
        assert c.post(url+'/open', json={'cell': i}).status_code == 200
        result = c.post(url+'/answer', json={'cell': i, 'answer': clue['answer']}).json()
    assert result['status'] == 'finished' and result['score'] == 7500 and result['played'] == 25
    assert c.post(url+'/finish', json={}).json()['score'] == 7500
    assert c.get(f'/api/trivia/players/{player["id"]}/active').json() is None


def test_invalid_generation_fails_without_partial_board(trivia):
    c, _, _, provider, player = trivia
    provider.generate = lambda _: demo_pack()[:24]
    game = create(c, player, False).json()
    failed = c.get(f'/api/trivia/games/{game["id"]}').json()
    assert failed['status'] == 'failed' and not failed['cells'] and failed['error']


def test_spoken_demo_aliases_are_accepted_without_a_model(trivia):
    c, _, _, provider, player = trivia
    provider.configured = False
    game = create(c, player).json()
    url = f'/api/trivia/games/{game["id"]}'
    for cell, answer in [(20, 'аш два о'), (5, 'пятьдесят шесть'), (1, 'два знака равно')]:
        c.post(url+'/open', json={'cell': cell})
        result = c.post(url+'/answer', json={'cell': cell, 'answer': answer}).json()
        assert result['results'][-1]['decision'] == 'correct'
    assert provider.checked == []


def test_pending_question_survives_server_restart(trivia):
    c, app, clock, _, player = trivia
    game = create(c, player).json()
    url = f'/api/trivia/games/{game["id"]}'
    c.post(url+'/open', json={'cell': 0})
    clock[0] = 1020
    app.state.initialize()
    assert c.get(url).json()['pending']['deadline'] == 1060


@pytest.mark.parametrize('a,b,same', [('3,14', '3.14', True), ('314', '3.14', False),
    ('C#', 'C', False), ('!', '==', False), ('Это Меркурий.', 'меркурий', True),
    ('Не Меркурий', 'Меркурий', False), ('<a>', 'a', False), ('-3', '3', False)])
def test_exact_answers_preserve_numbers_code_and_negation(a,b,same):
    assert (normalize(a) == normalize(b)) == same


def test_model_response_adapter_has_strict_schema_and_does_not_store(monkeypatch):
    import httpx
    monkeypatch.setenv('OPENAI_API_KEY', 'unit-test-key')
    captured = {}
    def post(url, **kwargs):
        captured.update(kwargs['json'])
        if captured['text']['format']['name'] == 'EditorialReview':
            return httpx.Response(200, json={'status':'completed','output':[{'content':[
                {'type':'output_text','text':json.dumps({'issues':[]})}]}]})
        return httpx.Response(200, json={'status': 'completed', 'output': [{'content': [
            {'type': 'output_text', 'text': json.dumps({'clues': demo_pack()})}]}]})
    monkeypatch.setattr(httpx, 'post', post)
    assert len(OpenAIQuiz().generate(DEMO_TOPICS)) == 25
    assert captured['model'] == 'gpt-5.4' and captured['store'] is False
    assert captured['text']['format']['strict'] and captured['text']['format']['type'] == 'json_schema'
