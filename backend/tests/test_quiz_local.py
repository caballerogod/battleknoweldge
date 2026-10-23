import json
import httpx
import pytest
from app.quiz_local import OllamaQuiz, quiz_provider, URL, cells_schema
from app.quiz_ai import Verdict, EditorialReview, OpenAIQuiz
from app.ai_usage import usage_summary
from app.trivia_party_demo import party_demo, PARTY_TOPICS
from app.trivia import demo_pack


def test_provider_selection_is_explicit_no_paid_fallback(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER','ollama')
    assert isinstance(quiz_provider(),OllamaQuiz)
    monkeypatch.setenv('AI_PROVIDER','openai')
    assert type(quiz_provider()) is OpenAIQuiz
    monkeypatch.setenv('AI_PROVIDER','typo')
    with pytest.raises(RuntimeError): quiz_provider()


@pytest.mark.parametrize('names,ready', [([],False),(['qwen3:4b-instruct'],True)])
def test_availability_checks_installed_model(monkeypatch,names,ready):
    monkeypatch.setenv('OLLAMA_MODEL','qwen3:4b-instruct')
    def get(url,**kwargs):
        assert url==URL+'/api/tags' and kwargs['trust_env'] is False
        return httpx.Response(200,json={'models':[{'name':n} for n in names]},request=httpx.Request('GET',url))
    monkeypatch.setattr(httpx,'get',get)
    assert OllamaQuiz().configured is ready


def test_offline_service_does_not_attempt_openai(monkeypatch):
    def get(url,**kwargs):
        assert url.startswith(URL)
        raise httpx.ConnectError('offline')
    monkeypatch.setattr(httpx,'get',get)
    assert OllamaQuiz().configured is False


def test_cloud_model_is_rejected_before_any_request(monkeypatch):
    monkeypatch.setenv('OLLAMA_MODEL','qwen3:480b-cloud')
    monkeypatch.setattr(httpx,'post',lambda *a,**kw:pytest.fail('Cloud request forbidden'))
    assert not OllamaQuiz().configured
    with pytest.raises(RuntimeError,match='cloud'):
        OllamaQuiz().request('Проверь',{},Verdict,800)


@pytest.mark.parametrize('mode',['ok','bad_json','timeout','http_error','truncated'])
def test_local_structured_request_costs_zero_even_on_failure(monkeypatch,mode):
    calls=[]
    def post(url,**kwargs):
        calls.append(url)
        assert usage_summary()['unpriced_requests']==0
        assert url==URL+'/api/chat'
        assert 'Authorization' not in kwargs.get('headers',{})
        assert kwargs['trust_env'] is False
        assert kwargs['json']['format']==Verdict.model_json_schema()
        if mode=='timeout': raise httpx.ReadTimeout('slow')
        return httpx.Response(500 if mode=='http_error' else 200,
            json={'done':True,'done_reason':'length' if mode=='truncated' else 'stop',
                  'prompt_eval_count':50,'eval_count':20,
                  'message':{'content':'broken' if mode=='bad_json' else json.dumps({'decision':'correct','explanation':'Верно'})}},
            request=httpx.Request('POST',url))
    monkeypatch.setattr(httpx,'post',post)
    if mode=='ok': assert OllamaQuiz().request('Проверь',{},Verdict,800)['decision']=='correct'
    else:
        with pytest.raises(RuntimeError): OllamaQuiz().request('Проверь',{},Verdict,800)
    assert calls==[URL+'/api/chat']
    usage=usage_summary()
    assert usage['estimated_usd']==0 and usage['unpriced_requests']==0
    assert usage['requests']==1 and usage['by_model'][0]['model'].startswith('ollama/')


def test_topic_batches_keep_good_topics_and_repair_only_failed_topic(monkeypatch):
    pack=party_demo(demo_pack())
    monkeypatch.setattr('app.quiz_local.format_plan',lambda topics:[{k:q[k] for k in ('topic_index','price','kind','image_id')} for q in pack])
    # Demo questions are fixtures; this test covers batching, not model quality.
    monkeypatch.setattr('app.quiz_local.obvious_issues',lambda *args:[])
    seen=[];reviews={}
    def request(self,instructions,data,schema,tokens):
        idx=data['topic_index'];seen.append((schema,idx))
        if schema is EditorialReview:
            reviews[idx]=reviews.get(idx,0)+1
            return {'issues':[{'topic_index':idx,'price':100,'reason':'Исправить факт'}] if idx==2 and reviews[idx]==1 else []}
        keys=set(schema.model_fields)
        if idx==2 and reviews.get(idx)==1: assert keys=={'q100'}
        return {f"q{q['price']}":q for q in pack if q['topic_index']==idx and f"q{q['price']}" in keys}
    monkeypatch.setattr(OllamaQuiz,'request',request)
    progress=[]
    result=OllamaQuiz().generate(PARTY_TOPICS,on_progress=progress.append)
    assert len(result)==40
    assert any('Тема 8 из 8' in message for message in progress)
    assert any('Исправляем тему 3' in message for message in progress)
    assert [i for schema,i in seen if schema is not EditorialReview]==[0,1,2,2,3,4,5,6,7]


def test_repair_is_bounded(monkeypatch):
    pack=party_demo(demo_pack())
    monkeypatch.setattr('app.quiz_local.format_plan',lambda topics:[{k:q[k] for k in ('topic_index','price','kind','image_id')} for q in pack])
    monkeypatch.setattr('app.quiz_local.obvious_issues',lambda *args:[{'reason':'Ошибка'}])
    calls=[]
    def request(*args):
        calls.append(1)
        schema=args[3]
        return {f"q{q['price']}":q for q in pack if q['topic_index']==0 and f"q{q['price']}" in schema.model_fields}
    monkeypatch.setattr(OllamaQuiz,'request',request)
    with pytest.raises(RuntimeError,match='трёх попыток'): OllamaQuiz().generate(PARTY_TOPICS)
    assert len(calls)==3


def test_slot_schema_rejects_model_swapping_format_or_price():
    pack=party_demo(demo_pack())
    clue=pack[0]
    plan=[{k:clue[k] for k in ('topic_index','price','kind','image_id')}]
    schema=cells_schema(0,plan,[100],True)
    assert schema.model_validate({'q100':clue})
    with pytest.raises(ValueError):
        schema.model_validate({'q100':{**clue,'price':200}})
    with pytest.raises(ValueError):
        schema.model_validate({'q100':{**clue,'kind':'unexpected'}})
