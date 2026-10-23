"""Durable local usage ledger. Stores metadata only, never prompts, answers or keys."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4
import logging
import os
import re
import sqlite3
import time

GAME = ContextVar('quiz_usage_game', default=None)
PRICING_DATE = '2026-10-23'
# USD per million tokens: input, cached input, output (reasoning included).
RATES = {'gpt-5.4-mini': (.75, .075, 4.5), 'gpt-5.4': (2.5, .25, 15.)}


@contextmanager
def usage_scope(game_id):
    token = GAME.set(game_id)
    try:
        yield
    finally:
        GAME.reset(token)


@contextmanager
def connect():
    path = Path(os.getenv('AI_USAGE_DB') or Path(__file__).resolve().parent.parent / 'ai_usage.db')
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS ai_requests (
        id TEXT PRIMARY KEY, game_id TEXT, created_at REAL NOT NULL,
        stage TEXT NOT NULL, requested_model TEXT NOT NULL, model TEXT NOT NULL,
        status TEXT NOT NULL, response_id TEXT, http_status INTEGER,
        input_tokens INTEGER, cached_input_tokens INTEGER, output_tokens INTEGER,
        reasoning_tokens INTEGER, estimated_usd REAL, pricing_date TEXT NOT NULL,
        elapsed_ms INTEGER, service_tier TEXT
    )''')
    db.execute('CREATE INDEX IF NOT EXISTS ai_requests_game ON ai_requests(game_id)')
    db.commit()
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def start_request(model, stage, *, local=False):
    request_id = str(uuid4())
    try:
        with connect() as db:
            db.execute('''INSERT INTO ai_requests
                (id,game_id,created_at,stage,requested_model,model,status,pricing_date,estimated_usd,service_tier)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (request_id,GAME.get(),time.time(),stage,model,model,'started',PRICING_DATE,
                 0 if local else None,'local' if local else None))
    except (sqlite3.Error,OSError):
        raise RuntimeError('Не удалось открыть журнал расходов API. Запрос не отправлен.') from None
    return request_id


def usage_details(usage):
    if not isinstance(usage, dict):
        return None
    incoming, outgoing = usage.get('input_tokens'), usage.get('output_tokens')
    incoming_details=usage.get('input_tokens_details') or {}
    outgoing_details=usage.get('output_tokens_details') or {}
    if not isinstance(incoming_details,dict) or not isinstance(outgoing_details,dict):
        return None
    cached = incoming_details.get('cached_tokens',0)
    reasoning = outgoing_details.get('reasoning_tokens',0)
    values = (incoming,cached,outgoing,reasoning)
    if any(type(v) is not int or v < 0 for v in values) or cached>incoming or reasoning>outgoing:
        return None
    return values


def estimate_usd(model, usage, service_tier='default'):
    values=usage_details(usage)
    if not isinstance(model,str):
        return None
    family=next((name for name in RATES if re.fullmatch(re.escape(name)+r'(?:-\d{4}-\d{2}-\d{2})?',model)),None)
    if not family or not values or service_tier not in ('default','auto',None):
        return None
    incoming,cached,outgoing,_=values
    ir,cr,orr=RATES[family]
    if family=='gpt-5.4' and incoming>272000:
        ir,cr,orr=ir*2,cr*2,orr*1.5
    return round(((incoming-cached)*ir+cached*cr+outgoing*orr)/1_000_000,9)


def finish_request(request_id, model, status, elapsed_ms, body=None, http_status=None):
    body=body if isinstance(body,dict) else {}
    reported=body.get('model')
    valid_model=reported is None or isinstance(reported,str) and bool(reported.strip())
    actual=reported if isinstance(reported,str) and reported.strip() else model
    raw_tier=body.get('service_tier','default')
    tier=raw_tier if isinstance(raw_tier,str) else None
    usage=body.get('usage')
    values=usage_details(usage) or (None,None,None,None)
    cost=estimate_usd(actual,usage,tier) if valid_model and (raw_tier is None or isinstance(raw_tier,str)) else None
    response_id=body.get('id') if isinstance(body.get('id'),str) else None
    try:
        with connect() as db:
            db.execute('''UPDATE ai_requests SET model=?,status=?,response_id=?,http_status=?,
                input_tokens=?,cached_input_tokens=?,output_tokens=?,reasoning_tokens=?,
                estimated_usd=?,elapsed_ms=?,service_tier=? WHERE id=?''',
                (actual,status,response_id,http_status,*values,cost,elapsed_ms,tier,request_id))
    except (sqlite3.Error,OSError):
        # The durable started row remains visible as an unknown-cost attempt.
        logging.getLogger(__name__).warning('Could not finalize API usage row; cost remains unknown.')


def usage_summary(game_id=None):
    try:
        with connect() as db:
            rows=db.execute('''SELECT model,stage,COUNT(*) requests,
                SUM(input_tokens) input_tokens,SUM(cached_input_tokens) cached_input_tokens,
                SUM(output_tokens) output_tokens,SUM(reasoning_tokens) reasoning_tokens,
                SUM(estimated_usd) estimated_usd,
                SUM(CASE WHEN estimated_usd IS NULL THEN 1 ELSE 0 END) unpriced_requests
                FROM ai_requests '''+('WHERE game_id=? ' if game_id else '')+
                'GROUP BY model,stage', (game_id,) if game_id else ()).fetchall()
        groups=[dict(row) for row in rows]
        totals={key:sum(row[key] or 0 for row in groups) for key in
                ('requests','input_tokens','cached_input_tokens','output_tokens','reasoning_tokens',
                 'estimated_usd','unpriced_requests')}
        totals['estimated_usd']=round(totals['estimated_usd'],9)
        return dict(available=True,complete=totals['unpriced_requests']==0,
                    pricing_date=PRICING_DATE,by_model=groups,**totals)
    except (sqlite3.Error,OSError):
        return dict(available=False,complete=False,estimated_usd=None,requests=0,
                    unpriced_requests=0,by_model=[],pricing_date=PRICING_DATE)


def finish_local_request(request_id, status, elapsed_ms, body=None):
    """Only the loopback Ollama adapter uses this: no metered API is contacted."""
    body = body if isinstance(body, dict) else {}
    counts = [body.get('prompt_eval_count'), body.get('eval_count')]
    counts = [v if type(v) is int and v >= 0 else None for v in counts]
    try:
        with connect() as db:
            db.execute('''UPDATE ai_requests SET status=?,input_tokens=?,output_tokens=?,
                estimated_usd=0,elapsed_ms=?,service_tier='local' WHERE id=?''',
                (status,*counts,elapsed_ms,request_id))
    except (sqlite3.Error,OSError):
        logging.getLogger(__name__).warning('Could not finalize local inference usage.')
