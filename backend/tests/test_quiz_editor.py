import copy
import pytest
from app.quiz_ai import OpenAIQuiz, EditorialReview, Pack
from app.quiz_editor import obvious_issues
from app.trivia import DEMO_TOPICS, demo_pack


def test_obvious_filter_topic_answer_and_embedded_answer():
    clues = [
        dict(topic_index=0, price=100, question='В какую игру играют с мячом и кольцом?', answer='Баскетбол'),
        dict(topic_index=1, price=200, question='Почему Юпитер называют газовым гигантом?', answer='Юпитер'),
        dict(topic_index=0, price=300, question='Сколько очков даёт штрафной бросок?', answer='1'),
    ]
    issues = obvious_issues(['Баскетбол', 'Космос'], clues)
    assert {(x['topic_index'], x['price']) for x in issues} == {(0,100),(1,200)}


def test_editor_replaces_bad_clue_and_rechecks(monkeypatch):
    original = demo_pack()
    repaired = copy.deepcopy(original)
    repaired[0]['question'] = 'Какой оператор Python проверяет принадлежность элемента коллекции?'
    repaired[0]['answer'] = 'in'
    sequence = [
        (Pack, {'clues':original}),
        (EditorialReview, {'issues':[dict(topic_index=0,price=100,reason='Банальное определение')]}),
        (Pack, {'clues':repaired}),
        (EditorialReview, {'issues':[]}),
    ]
    calls = []
    def request(self, instructions, data, schema, tokens):
        expected, result = sequence.pop(0)
        assert schema is expected
        calls.append(data)
        return result
    monkeypatch.setattr(OpenAIQuiz, 'request', request)
    result = OpenAIQuiz().generate(DEMO_TOPICS)
    assert result[0] == repaired[0]
    assert calls[2]['issues'][0]['reason'] == 'Банальное определение'
    assert not sequence


def test_quality_failure_is_bounded_and_never_returns_bad_board(monkeypatch):
    calls = []
    def request(self, instructions, data, schema, tokens):
        calls.append(schema)
        if schema is Pack:
            return {'clues':demo_pack()}
        return {'issues':[dict(topic_index=0,price=500,reason='Несправедливая сложность')]}
    monkeypatch.setattr(OpenAIQuiz, 'request', request)
    with pytest.raises(RuntimeError, match='редакторскую проверку'):
        OpenAIQuiz().generate(DEMO_TOPICS)
    assert calls == [Pack, EditorialReview, Pack, EditorialReview]


def test_local_filter_cannot_be_overruled_by_empty_model_review(monkeypatch):
    clues = demo_pack()
    clues[0]['answer'] = DEMO_TOPICS[0]
    def request(self, instructions, data, schema, tokens):
        return {'clues':clues} if schema is Pack else {'issues':[]}
    monkeypatch.setattr(OpenAIQuiz, 'request', request)
    with pytest.raises(RuntimeError, match='редакторскую проверку'):
        OpenAIQuiz().generate(DEMO_TOPICS)
