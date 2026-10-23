import copy
import pytest
from app.quiz_ai import OpenAIQuiz, EditorialReview, addressed_schema
from app.trivia import demo_pack
from app.trivia_party_demo import PARTY_TOPICS,party_demo


def fixture_board(monkeypatch):
    clues=party_demo(demo_pack())
    plan=[{k:q[k] for k in ('topic_index','price','kind','image_id')} for q in clues]
    monkeypatch.setattr('app.quiz_ai.obvious_issues',lambda *args:[])
    return clues,{'topics':PARTY_TOPICS,'plan':plan}


def test_addressed_repairs_preserve_39_accepted_cells(monkeypatch):
    original,context=fixture_board(monkeypatch)
    replacement=copy.deepcopy(original[0]);replacement['question']='Новая однозначная формулировка того же вопроса?'
    calls=[]
    def request(self,instructions,data,schema,tokens):
        calls.append((schema,data))
        if schema is EditorialReview:
            return {'issues':[dict(topic_index=0,price=100,reason='Неточность')] if len(calls)==1 else []}
        assert schema.__name__=='AddressedRepairs' and len(data['clues'])==1
        return {'q0_100':replacement}
    monkeypatch.setattr(OpenAIQuiz,'request',request)
    result=OpenAIQuiz().edit_mixed(PARTY_TOPICS,copy.deepcopy(original),context,'Правила')
    assert result[0]==replacement and result[1:]==original[1:]
    assert len(calls[2][1]['clues'])==1


def test_repeated_rejection_is_bounded_without_accepting_bad_clues(monkeypatch):
    original,context=fixture_board(monkeypatch);calls=[]
    def request(self,instructions,data,schema,tokens):
        calls.append(schema)
        return {'issues':[dict(topic_index=0,price=100,reason='Ошибка')]} if schema is EditorialReview else {'q0_100':original[0]}
    monkeypatch.setattr(OpenAIQuiz,'request',request)
    result=OpenAIQuiz().edit_mixed(PARTY_TOPICS,original,context,'Правила')
    assert result==original and len(result.editorial_notes)==1
    assert sum(s.__name__=='AddressedRepairs' for s in calls)==1 and calls.count(EditorialReview)==2


def test_repair_must_match_requested_cells(monkeypatch):
    original,context=fixture_board(monkeypatch)
    def request(self,instructions,data,schema,tokens):
        return {'issues':[dict(topic_index=0,price=100,reason='Ошибка')]} if schema is EditorialReview else {'q0_200':original[1]}
    monkeypatch.setattr(OpenAIQuiz,'request',request)
    result=OpenAIQuiz().edit_mixed(PARTY_TOPICS,original,context,'Правила')
    assert result==original and result.editorial_notes[0]['price']==100


def test_addressed_schema_locks_metadata(monkeypatch):
    original,_=fixture_board(monkeypatch)
    schema=addressed_schema([original[0]])
    assert schema.model_validate({'q0_100':original[0]})
    with pytest.raises(ValueError):
        schema.model_validate({'q0_100':{**original[0],'price':200}})
    with pytest.raises(ValueError):
        schema.model_validate({'q0_100':{**original[0],'image_id':'unvetted'}})
