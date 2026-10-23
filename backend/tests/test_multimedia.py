"""Offline integration coverage for model schemas, curated media and live game transport."""
import copy
import json
import random
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.quiz_ai import OpenAIQuiz, MixedPack, EditorialReview, Verdict, addressed_schema, validate_pack
from app.quiz_editor import obvious_issues
from app.quiz_local import cells_schema
from app.trivia_media import MEDIA_CATALOG, SPECIAL_TOPICS, format_plan, public_media, topic_style, validate_mixed
from app.trivia_party_demo import MEDIA_CLUES

TOPICS=[*SPECIAL_TOPICS,'Музыка','Космос','Наука','Кино','Математика']

def authored_pack(plan):
    result=[]
    binary=[('Можно ли услышать звук в идеальном вакууме?','Нет'),('Земля слегка сплюснута у полюсов?','Да'),('Световой год — единица времени?','Нет'),('При одинаковой температуре металл может ощущаться холоднее дерева?','Да'),('Все металлы при комнатной температуре твёрдые?','Нет')]
    for slot in plan:
        t,p,kind,key=slot['topic_index'],slot['price'],slot['kind'],slot['image_id']
        q=dict(**slot,question=f'Учебный вопрос {t+1}.{p//100}: назовите подходящее понятие.',answer='Тестовое понятие',aliases=[],explanation='Это проверочная формулировка для локального тестирования транспорта.',options=[])
        if kind=='image' and key in MEDIA_CATALOG:
            q.update(question=f'Назовите сериал по скрытому фрагменту №{t+1}.{p//100}.',answer=MEDIA_CATALOG[key]['reference'])
        elif kind=='yesno':
            question,answer=binary[p//100-1];q.update(question=question,answer=answer,options=['Да','Нет'])
        elif kind=='linked':
            q.update(question=f'Загадка №{p//100}: 1) Растворитель лака. 2) Смесь цемента с заполнителями. 3) Плотная бумага для коробок.',answer='ацетон;бетон;картон',explanation='Ацетон — растворитель, бетон — строительный материал, картон — упаковка. В каждом есть «тон».')
        elif kind in {'audio','video'}:
            question,answer,aliases,explanation=MEDIA_CLUES[key];q.update(question=question+f' Задание {t+1}.{p//100}.',answer=answer,aliases=aliases,explanation=explanation)
        elif kind=='image':
            # For the contract tests the prompt is not intended as a real quiz.
            q.update(question=f'Какое понятие обозначает схема №{t+1}.{p//100}?')
        elif kind=='choice':q.update(options=['Тестовое понятие','Другой термин','Третий термин','Четвёртый термин'])
        result.append(q)
    return validate_pack({'clues':validate_mixed(result,plan)},8)


def test_special_plans_preserve_five_distinct_series_and_binary_topics():
    plan=format_plan(TOPICS,random.Random(8))
    assert len(plan)==40
    assert len({MEDIA_CATALOG[q['image_id']]['reference'] for q in plan[:5]})==5
    assert all(q['kind']=='linked' for q in plan[5:10])
    assert all(q['kind']=='yesno' for q in plan[10:15])
    assert {'audio','video'}<={q['kind'] for q in plan}
    assert topic_style('Кадры из сериалов (через сильное размытие или пиксели)')=='frames'
    assert topic_style('Бытовая загадка')=='linked'
    assert topic_style('Да/нет')=='yesno'
    assert topic_style('Химия')==''


@pytest.mark.parametrize('kind,key',[('audio','https://example.com/clip.mp3'),('video','../../secret'),('audio','v01'),('video','a01')])
def test_generated_media_cannot_invent_urls_or_swap_types(kind,key):
    q=authored_pack(format_plan(TOPICS,random.Random(1)))[0]
    q.update(kind=kind,image_id=key,options=[])
    with pytest.raises(ValueError):validate_mixed([q],expected_count=1)


def test_binary_and_linked_contracts_and_repair_schemas():
    clues=authored_pack(format_plan(TOPICS,random.Random(1)))
    binary=clues[10]
    assert addressed_schema([binary]).model_validate({'q2_100':binary})
    slots=[{k:q[k] for k in ('topic_index','price','kind','image_id')} for q in clues[10:15]]
    local=cells_schema(2,slots,[100],True)
    assert local.model_validate({'q100':binary})
    with pytest.raises(ValueError):validate_mixed([{**binary,'options':['Да','Нет','Возможно','Не знаю']}],expected_count=1)
    linked=clues[5]
    with pytest.raises(ValueError):validate_mixed([{**linked,'answer':'ацетон;лампа;вода'}],expected_count=1)
    with pytest.raises(ValueError):validate_mixed([{**linked,'question':'Только одна подсказка вместо трёх.'}],expected_count=1)
    all_no=[{**q,'answer':'Нет'} for q in clues[10:15]]
    assert any('Все пять' in issue['reason'] for issue in obvious_issues(TOPICS,all_no))


def test_public_media_hides_sources_and_references_until_reveal():
    clue=authored_pack(format_plan(TOPICS,random.Random(1)))[0]
    hidden=public_media(clue)
    assert set(hidden)=={'url','kind','mask','level','hint'} and hidden['mask']!='none'
    revealed=public_media(clue,True)
    assert revealed['mask']=='none' and revealed['credit'] and revealed['source'].startswith('https://www.netflix.com/')


def test_all_local_assets_exist_small_and_have_expected_signatures():
    root=Path(__file__).resolve().parents[2]/'frontend/public'
    total=0
    for asset in MEDIA_CATALOG.values():
        data=(root/asset['url'].lstrip('/')).read_bytes();total+=len(data)
        assert len(data)>1000
        assert data[:2]==b'\xff\xd8' if asset['kind']=='image' else data[:4]==b'RIFF' if asset['kind']=='audio' else data[4:8]==b'ftyp'
    assert total<8_000_000


def test_real_generation_adapter_and_40_turns_without_paid_calls(tmp_path,monkeypatch):
    calls=[]
    def request(self,instructions,data,schema,tokens):
        calls.append(schema)
        if schema is MixedPack:
            assert 'linked' in instructions and 'Не выдумывай' in instructions
            assert 'a01' in data['images'] and sum(bool(v.get('series')) for v in data['images'].values())==5
            return {'clues':authored_pack(data['plan'])}
        if schema is EditorialReview:return {'issues':[]}
        raise AssertionError('No grading or external request expected')
    monkeypatch.setattr(OpenAIQuiz,'request',request)
    monkeypatch.setattr(OpenAIQuiz,'configured',property(lambda _:True))
    clock=[1000.]
    app=create_app(f'sqlite:///{tmp_path/"media.db"}',clock=lambda:clock[0],quiz_provider=OpenAIQuiz())
    with TestClient(app) as c:
        player=c.post('/api/players',json={'nickname':'Media QA'}).json()
        game=c.post('/api/trivia/games',json=dict(player_id=player['id'],request_id=str(uuid4()),participants=['А','Б','В'],topics=TOPICS)).json()
        url='/api/trivia/games/'+game['id']
        game=c.get(url).json();assert game['status']=='ready',game['error']
        from sqlalchemy.orm import Session
        from app.models import TriviaGame
        with Session(app.state.engine) as db:clues=json.loads(db.get(TriviaGame,game['id']).pack)
        for i,q in enumerate(clues):
            opened=c.post(url+'/open',json={'cell':i}).json()
            assert opened['pending']['deadline']==1060
            assert 'correct_answer' not in opened['pending']
            if opened['pending']['media']:
                assert 'source' not in opened['pending']['media'] and 'reference' not in opened['pending']['media']
            if q['kind']=='yesno':
                assert c.post(url+'/answer',json={'cell':i,'answer':'Может быть'}).status_code==422
                # First binary answer is intentionally wrong to check a negative score.
                answer=('Нет' if q['answer']=='Да' else 'Да') if i==10 else q['answer']
            else:answer=q['answer']
            game=c.post(url+'/answer',json={'cell':i,'answer':answer}).json()
            assert game['played']==i+1 and game['current_participant']==(i+1)%3
            assert game['results'][-1]['decision']==('incorrect' if i==10 else 'correct')
            if i<5:assert game['results'][-1]['media']['mask']=='none'
        assert game['status']=='finished' and game['usage']['requests']==0
        assert calls==[MixedPack,EditorialReview]

def test_audio_video_never_repeat_and_stay_in_fair_price_range():
    for seed in range(100):
        plan=format_plan(['Музыка','Наука','Физика','Космос','История','Математика','Аудио','Видео'],random.Random(seed))
        media=[q for q in plan if q['kind'] in {'audio','video'}]
        assert len({q['image_id'] for q in media})==len(media)
        assert all(q['price']<=300 for q in media)
