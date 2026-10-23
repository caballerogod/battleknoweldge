import json
import sqlite3
import httpx
import pytest
from app.ai_usage import estimate_usd, start_request, finish_request, usage_scope, usage_summary
from app.quiz_ai import OpenAIQuiz, Verdict, Pack, EditorialReview
from app.trivia import demo_pack, DEMO_TOPICS

USAGE=dict(input_tokens=1000,input_tokens_details={'cached_tokens':400},
           output_tokens=200,output_tokens_details={'reasoning_tokens':50})


def test_prices_cache_reasoning_and_long_context():
    assert estimate_usd('gpt-5.4',USAGE)==pytest.approx(.0046)
    assert estimate_usd('gpt-5.4-mini',USAGE)==pytest.approx(.00138)
    assert estimate_usd('gpt-5.4-2026-03-05',USAGE)==pytest.approx(.0046)
    assert estimate_usd('unknown',USAGE) is None
    assert estimate_usd('gpt-5.4',None) is None
    assert estimate_usd('gpt-5.4',USAGE,'priority') is None
    assert estimate_usd('gpt-5.4',dict(input_tokens=10,output_tokens=0,
        input_tokens_details={'cached_tokens':11})) is None
    long=dict(input_tokens=300000,output_tokens=100,input_tokens_details={'cached_tokens':0})
    assert estimate_usd('gpt-5.4',long)==pytest.approx(1.50225)


def test_ledger_game_isolation_pending_unknown_and_repeated_finalization():
    with usage_scope('game-one'):
        first=start_request('gpt-5.4','generation')
        assert usage_summary('game-one')['unpriced_requests']==1
        finish_request(first,'gpt-5.4','completed',1,{'usage':USAGE},200)
        finish_request(first,'gpt-5.4','completed',1,{'usage':USAGE},200)
    with usage_scope('game-two'):
        second=start_request('gpt-5.4-mini','grading')
        finish_request(second,'gpt-5.4-mini','transport_error',1)
    one=usage_summary('game-one');two=usage_summary('game-two');total=usage_summary()
    assert one['requests']==1 and one['complete'] and one['estimated_usd']==pytest.approx(.0046)
    assert one['output_tokens']==200 and one['reasoning_tokens']==50
    assert two['requests']==1 and not two['complete']
    assert total['requests']==2 and total['unpriced_requests']==1
    assert total['estimated_usd']==one['estimated_usd']


def test_routing_all_stages_and_usage_without_prompt_storage(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-key-never-log')
    monkeypatch.setenv('OPENAI_GENERATION_MODEL','gpt-5.4')
    monkeypatch.setenv('OPENAI_REVIEW_MODEL','gpt-5.4')
    monkeypatch.setenv('OPENAI_GRADING_MODEL','gpt-5.4-mini')
    captured=[]
    def post(url,**kwargs):
        data=kwargs['json'];captured.append(data)
        name=data['text']['format']['name']
        out={'decision':'correct','explanation':'Верно'} if name=='Verdict' else (
            {'issues':[]} if name=='EditorialReview' else {'clues':demo_pack()})
        return httpx.Response(200,json={'id':'response-'+str(len(captured)),'status':'completed',
            'model':data['model'],'service_tier':'default','usage':USAGE,
            'output':[{'content':[{'type':'output_text','text':json.dumps(out)}]}]})
    monkeypatch.setattr(httpx,'post',post)
    q=OpenAIQuiz()
    with usage_scope('routed'):
        q.generate(DEMO_TOPICS)
        q.grade('секретный ответ',demo_pack()[0])
        q.request('repair',{'issues':[]},Pack,1000)
    assert [x['model'] for x in captured]==['gpt-5.4','gpt-5.4','gpt-5.4-mini','gpt-5.4']
    assert all(x['store'] is False and x['service_tier']=='default' for x in captured)
    summary=usage_summary('routed')
    assert summary['requests']==4 and summary['complete']
    assert {x['stage'] for x in summary['by_model']}=={'generation','review','grading','repair'}
    import os
    db=sqlite3.connect(os.environ['AI_USAGE_DB'])
    columns={r[1] for r in db.execute('pragma table_info(ai_requests)')}
    assert not columns & {'prompt','answer','api_key','headers','instructions'}
    assert 'секретный ответ' not in str(db.execute('select * from ai_requests').fetchall())
    db.close()


@pytest.mark.parametrize('kind',['incomplete','invalid_output','http_error','timeout'])
def test_failures_remain_in_usage_even_if_no_playable_output(monkeypatch,kind):
    monkeypatch.setenv('OPENAI_API_KEY','test-key')
    def post(url,**kwargs):
        if kind=='timeout':
            raise httpx.ReadTimeout('timeout')
        return httpx.Response(429 if kind=='http_error' else 200,json={
            'model':'gpt-5.4-mini','status':'incomplete' if kind=='incomplete' else 'completed',
            'usage':USAGE,'output':[{'content':[{'type':'output_text','text':'not json'}]}]})
    monkeypatch.setattr(httpx,'post',post)
    with usage_scope('failed'):
        with pytest.raises(RuntimeError):
            OpenAIQuiz().grade('любой ответ',demo_pack()[0])
    summary=usage_summary('failed')
    assert summary['requests']==1
    assert summary['unpriced_requests']==(1 if kind=='timeout' else 0)
    if kind!='timeout':
        assert summary['estimated_usd']==pytest.approx(.00138)


def test_usage_endpoints_do_not_expose_key_or_question_text(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app=create_app(f'sqlite:///{tmp_path/"app.db"}')
    with TestClient(app) as c:
        config=c.get('/api/trivia/config').json()
        assert config['models']==dict(generation='gpt-5.4',review='gpt-5.4',grading='gpt-5.4-mini')
        assert config['usage']['requests']==0
        assert c.get('/api/trivia/usage').json()['available']
        assert 'OPENAI_API_KEY' not in json.dumps(config)


def test_ledger_failure_prevents_paid_request(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-key')
    monkeypatch.setenv('AI_USAGE_DB',str(tmp_path/'missing'/'usage.db'))
    sent=[]
    monkeypatch.setattr(httpx,'post',lambda *a,**k:sent.append(True))
    with pytest.raises(RuntimeError,match='Запрос не отправлен'):
        OpenAIQuiz().grade('ответ',demo_pack()[0])
    assert not sent

def test_pro_model_must_not_use_standard_54_price():
    assert estimate_usd('gpt-5.4-pro',USAGE) is None
    assert estimate_usd('gpt-5.4-pro-2026-03-05',USAGE) is None


def test_malformed_model_metadata_does_not_discard_valid_verdict(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-key')
    monkeypatch.setattr(httpx,'post',lambda *a,**k:httpx.Response(200,json={
        'model':{'unexpected':'object'},'status':'completed','usage':USAGE,
        'output':[{'content':[{'type':'output_text','text':json.dumps({'decision':'correct','explanation':'Верно'})}]}]}))
    with usage_scope('malformed-metadata'):
        assert OpenAIQuiz().grade('ответ',demo_pack()[0])['decision']=='correct'
    summary=usage_summary('malformed-metadata')
    assert summary['requests']==1 and summary['unpriced_requests']==1


def test_malformed_output_is_a_controlled_error_and_usage_is_recorded(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-key')
    monkeypatch.setattr(httpx,'post',lambda *a,**k:httpx.Response(200,json={
        'model':'gpt-5.4-mini','status':'completed','usage':USAGE,'output':[None]}))
    with usage_scope('malformed-output'):
        with pytest.raises(RuntimeError,match='некорректные данные'):
            OpenAIQuiz().grade('ответ',demo_pack()[0])
    assert usage_summary('malformed-output')['estimated_usd']==pytest.approx(.00138)
