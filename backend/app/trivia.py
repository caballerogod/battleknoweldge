import json
from uuid import UUID, uuid4
from fastapi import BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .models import Player, TriviaGame
from .questions import BANK
from .ai_usage import usage_scope, usage_summary
from .trivia_media import image_url, validate_mixed, public_media, SPECIAL_TOPICS
from .trivia_party_demo import PARTY_TOPICS, party_demo
from .quiz_ai import OpenAIQuiz, exact_answer, validate_pack, settings
from .quiz_local import quiz_provider, OllamaQuiz
from .presentation_bank import catalog as presentation_catalog, presentation_pack

DEMO_TOPICS = ['Программирование', 'Математика', 'История', 'География', 'Наука']
DEMO_ALIASES = {
    'int': ['инт', 'интеджер', 'тип int'],
    '==': ['равно равно', 'двойное равно', 'два знака равно'],
    'O(log n)': ['логарифмическая', 'логарифмическая сложность', 'о от логарифма эн', 'o(logn)'],
    'PUT': ['пут', 'метод put'], 'Durability': ['долговечность', 'устойчивость'],
    '56': ['пятьдесят шесть'], '50': ['пятьдесят'],
    '2x': ['два икс', '2 икс', 'два x'], '5': ['пять'], '1/3': ['одна треть', 'треть'],
    'Древний Египет': ['Египет', 'в Древнем Египте', 'в Египте'],
    '1945': ['1945 год', 'в 1945 году', 'тысяча девятьсот сорок пятый', 'тысяча девятьсот сорок пятый год'],
    '1815': ['1815 год', 'в 1815 году', 'тысяча восемьсот пятнадцатый', 'тысяча восемьсот пятнадцатый год'],
    'Великая хартия вольностей': ['хартия вольностей', 'магна карта', 'magna carta'],
    'Вестфальский мир': ['Вестфальский мирный договор'],
    'Тихий': ['Тихий океан'], 'Африка': ['в Африке', 'на Африканском материке'],
    'Байкал': ['озеро Байкал'], 'Берингов': ['Берингов пролив'],
    'Меркатора': ['проекция Меркатора', 'Меркатор'],
    'H₂O': ['h2o', 'h 2 o', 'аш два о', 'аш 2 о'], 'Марс': ['планета Марс'],
    '300 000 км/с': ['300000 км/с', '300000 километров в секунду', '300 тысяч километров в секунду', 'триста тысяч километров в секунду', 'триста миллионов метров в секунду'],
    'Митохондрия': ['митохондрии'],
    'E = hν': ['e=hν', 'энергия равна постоянной Планка умноженной на частоту', 'е равно аш ню'],
}


class NewGame(BaseModel):
    player_id: int = Field(gt=0)
    request_id: UUID
    topics: list[str] = Field(min_length=5, max_length=8)
    participants: list[str] = Field(default_factory=list, max_length=3)
    demo: bool = False
    presentation: bool = False
    reserve: bool = False

    @field_validator('topics')
    @classmethod
    def topics_valid(cls, topics):
        topics = [' '.join(s.split()) for s in topics]
        if any(not 2 <= len(s) <= 70 for s in topics) or len({s.casefold() for s in topics}) != len(topics):
            raise ValueError('Нужны разные темы длиной от 2 до 70 символов')
        return topics


    @field_validator('participants')
    @classmethod
    def names_valid(cls, names):
        names = [' '.join(name.split()) for name in names]
        if names and (len(names) != 3 or any(not 1 <= len(n) <= 40 for n in names)
                      or len({n.casefold() for n in names}) != 3):
            raise ValueError('Введите три разных имени длиной до 40 символов')
        return names

    @model_validator(mode='after')
    def format_valid(self):
        if self.presentation and (self.demo or len(self.participants)!=3):
            raise ValueError('Для презентации нужны три участника; демо выбирается отдельно')
        if self.reserve and not self.presentation:
            raise ValueError('Резервный набор доступен в презентации')
        if len(self.topics) != (8 if self.participants else 5):
            raise ValueError('Для партии на троих нужны восемь тем; для прежней одиночной — пять')
        return self


class CellInput(BaseModel):
    cell: int = Field(ge=0, le=39)


class FreeAnswer(CellInput):
    answer: str | None = Field(default=None, max_length=500)
    skip: bool = False


class HostVerdict(CellInput):
    decision: str = Field(pattern='^(correct|incorrect|ambiguous)$')


def demo_pack():
    clues = []
    for t, topic in enumerate(DEMO_TOPICS):
        rows = [BANK[(topic, 'easy')][0], BANK[(topic, 'easy')][1],
                BANK[(topic, 'medium')][0], BANK[(topic, 'medium')][1], BANK[(topic, 'hard')][0]]
        for p, row in enumerate(rows):
            clues.append(dict(topic_index=t, price=(p+1)*100, question=row[0], answer=row[1],
                              aliases=DEMO_ALIASES.get(row[1], []), explanation=row[5]))
    return validate_pack({'clues': clues})


def register_trivia(app, engine, clock, provider=None):
    ai = provider or quiz_provider()
    app.state.quiz_ai = ai
    generation_progress = {}

    def recover_jobs():
        # A process restart cannot resume in-memory BackgroundTasks. Keep submitted text intact.
        with Session(engine) as db:
            for g in db.scalars(select(TriviaGame).where(TriviaGame.status.in_(['generating', 'ready']))):
                if g.status == 'generating':
                    g.status, g.error = 'failed', 'Подготовка прервана перезапуском сервера. Создайте новую партию.'
                elif g.pending:
                    pending = json.loads(g.pending)
                    if pending.get('grading'):
                        pending.update(grading=False, grade_error='Проверка прервана. Повторите её: ответ сохранён, штрафа нет.')
                        g.pending = json.dumps(pending, ensure_ascii=False)
            db.commit()
    app.state.recover_trivia_jobs = recover_jobs

    def db_session():
        with Session(engine) as db:
            yield db

    def require(db, sid):
        game = db.get(TriviaGame, sid)
        if not game:
            raise HTTPException(404, 'Партия не найдена')
        return game

    def notes_for(g, cell=None):
        notes=json.loads(g.editorial_notes or '[]')
        if cell is None:
            return notes
        return [n for n in notes if n['topic_index']==cell//5 and n['price']==(cell%5+1)*100]

    def has_playable_draft(g):
        if g.status!='failed':
            return False
        try:
            clues=validate_pack({'clues':json.loads(g.pack)},len(json.loads(g.topics)))
            return len(clues)==40 and bool(validate_mixed(clues))
        except (ValueError,KeyError,TypeError):
            return False

    def view(g):
        results, pack = json.loads(g.results), json.loads(g.pack)
        results=[{**r,'media':public_media(pack[r['cell']],reveal=True)} for r in results]
        pending = json.loads(g.pending) if g.pending else None
        done = {r['cell'] for r in results}
        public_pending = None
        names = json.loads(g.participants or '[]')
        current = len(results) % len(names) if names else 0
        if pending:
            public_pending = {key: pending[key] for key in ['cell', 'deadline', 'submitted', 'grading', 'grade_error']}
            public_pending.update(paused=pending.get('paused',False),remaining=pending.get('remaining'),time_limit=pending.get('time_limit',30))
            clue = pack[pending['cell']]
            public_pending.update(question=clue['question'], kind=clue.get('kind','open'),
                                  options=clue.get('options',[]), image_url=image_url(clue.get('image_id','')),
                                  participant=pending.get('participant',current),media=public_media(clue))
            if pending.get('manual') and pending['submitted'] is not None:
                public_pending.update(manual=True,correct_answer=clue['answer'],explanation=clue['explanation'])
                public_pending['review_note']=' '.join(n['reason'] for n in notes_for(g,pending['cell']))
            public_pending['host_review']=bool(notes_for(g,pending['cell']))
        return dict(id=g.id, player_id=g.player_id, topics=json.loads(g.topics), status=g.status,
                    demo=g.demo, error=g.error,
                    participants=[dict(name=name,score=sum(r['delta'] for r in results if r.get('participant',0)==i))
                                  for i,name in enumerate(names)],
                    current_participant=current, total=len(pack) or len(json.loads(g.topics))*5,
                    score=sum(r['delta'] for r in results),
                    played=len(results), cells=[dict(cell=i, topic_index=q['topic_index'], price=q['price'],
                                                   played=i in done) for i, q in enumerate(pack)],
                    pending=public_pending, results=results, server_time=clock(), usage=usage_summary(g.id),
                    progress=generation_progress.get(g.id,''),presentation=bool(g.presentation_meta),
                    presentation_info=json.loads(g.presentation_meta or '{}'),
                    host_review_count=len({(n['topic_index'],n['price']) for n in notes_for(g)}),
                    recoverable=has_playable_draft(g))

    def generate(sid):
        with Session(engine) as db:
            g = require(db, sid)
            topics = json.loads(g.topics)
        def save_draft(clues):
            with Session(engine) as draft_db:
                draft = require(draft_db,sid)
                if draft.status=='generating':
                    draft.pack=json.dumps(clues,ensure_ascii=False)
                    draft_db.commit()
        try:
            with usage_scope(sid):
                if isinstance(ai,OllamaQuiz):
                    generation_progress[sid] = 'Ожидаем свободную локальную модель…'
                    pack = ai.generate(topics,on_progress=lambda message:generation_progress.update({sid:message}))
                elif isinstance(ai,OpenAIQuiz):
                    generation_progress[sid] = 'GPT-5.4 составляет вопросы…'
                    pack = ai.generate(topics,on_progress=lambda message:generation_progress.update({sid:message}),on_draft=save_draft)
                else:
                    pack = ai.generate(topics)
                notes=getattr(pack,'editorial_notes',[])
                pack = validate_pack({'clues':pack},len(topics))
            if len(topics)==8:
                validate_mixed(pack)
            with Session(engine) as db:
                g = require(db, sid)
                g.pack, g.status = json.dumps(pack, ensure_ascii=False), 'ready'
                g.editorial_notes=json.dumps(notes,ensure_ascii=False)
                db.commit()
        except Exception as error:
            with Session(engine) as db:
                g = require(db, sid)
                g.status = 'failed'
                g.error = str(error) if isinstance(error, RuntimeError) else 'Не удалось подготовить корректные вопросы. Попробуйте другие темы.'
                db.commit()
        finally:
            generation_progress.pop(sid,None)

    def settle(db, g, pending, decision, reason=''):
        clue = json.loads(g.pack)[pending['cell']]
        delta = clue['price'] if decision == 'correct' else -clue['price'] if decision == 'incorrect' else 0
        results = json.loads(g.results)
        results.append(dict(cell=pending['cell'], participant=pending.get('participant',0), decision=decision, delta=delta,
                            answer=pending['submitted'] or '', correct_answer=clue['answer'],
                            question=clue['question'], explanation=clue['explanation'], review=reason))
        g.results, g.pending = json.dumps(results, ensure_ascii=False), None
        if len(results) == len(json.loads(g.pack)):
            g.status = 'finished'
        db.commit()

    def grade(sid, token):
        with Session(engine) as db:
            g = require(db, sid)
            pending = json.loads(g.pending) if g.pending else None
            if not pending or pending.get('token') != token:
                return
            clue = json.loads(g.pack)[pending['cell']]
            answer = pending['submitted']
        try:
            with usage_scope(sid):
                verdict = ai.grade(answer, clue)
            if verdict['decision'] not in {'correct', 'incorrect', 'ambiguous'}:
                raise RuntimeError('Не удалось уверенно проверить ответ.')
            with Session(engine) as db:
                db.execute(text('BEGIN IMMEDIATE'))
                g = require(db, sid)
                live = json.loads(g.pending) if g.pending else None
                if live and live.get('token') == token:
                    settle(db, g, live, verdict['decision'], verdict.get('explanation', ''))
        except Exception:
            with Session(engine) as db:
                db.execute(text('BEGIN IMMEDIATE'))
                g = require(db, sid)
                live = json.loads(g.pending) if g.pending else None
                if live and live.get('token') == token:
                    live['grading'] = False
                    live['grade_error'] = 'Проверка недоступна. Повторите проверку; ответ уже зафиксирован, штраф не начислен.'
                    g.pending = json.dumps(live, ensure_ascii=False)
                    db.commit()

    @app.get('/api/trivia/config')
    def config():
        config=settings()
        local=isinstance(ai,OllamaQuiz)
        ready,message=ai.availability() if local else (ai.configured,'')
        return dict(configured=ready, provider='ollama' if local else 'openai', message=message,
                    demo_topics=DEMO_TOPICS, party_demo_topics=PARTY_TOPICS,
                    presentation_topics=presentation_catalog(),suggested_topics=SPECIAL_TOPICS,
                    models={role:config['OLLAMA_MODEL'] if local else config['OPENAI_'+role.upper()+'_MODEL'] for role in ('generation','review','grading')},
                    usage=usage_summary())

    @app.get('/api/trivia/usage')
    def expenses():
        return usage_summary()

    @app.get('/api/trivia/players/{pid}/active')
    def active(pid: int, db: Session = Depends(db_session)):
        game = db.scalar(select(TriviaGame).where(TriviaGame.player_id == pid, TriviaGame.status.in_(['ready', 'generating'])).order_by(TriviaGame.created_at.desc()))
        return view(game) if game else None

    @app.post('/api/trivia/games')
    def create(payload: NewGame, tasks: BackgroundTasks, db: Session = Depends(db_session)):
        db.execute(text('BEGIN IMMEDIATE'))
        if not db.get(Player, payload.player_id):
            raise HTTPException(404, 'Игрок не найден')
        previous = db.scalar(select(TriviaGame).where(TriviaGame.request_id == str(payload.request_id)))
        if previous:
            if previous.player_id != payload.player_id:
                raise HTTPException(409, 'Идентификатор запроса уже использован')
            meta=json.loads(previous.presentation_meta or '{}')
            if bool(previous.presentation_meta)!=payload.presentation or meta.get('reserve_requested',False)!=payload.reserve or previous.demo != payload.demo or json.loads(previous.topics) != payload.topics or json.loads(previous.participants or '[]') != payload.participants:
                raise HTTPException(409, 'Повторный запрос должен содержать те же темы')
            return view(previous)
        if payload.demo and payload.topics != (PARTY_TOPICS if payload.participants else DEMO_TOPICS):
            raise HTTPException(422, 'Демонстрация использует готовый набор тем')
        if not payload.demo and not payload.presentation and not ai.configured:
            raise HTTPException(503, ai.availability()[1] if isinstance(ai,OllamaQuiz) else 'Генерация пока недоступна: на сервере не настроен OpenAI API-ключ. Можно сыграть демонстрационную партию.')
        g = TriviaGame(id=str(uuid4()), request_id=str(payload.request_id), player_id=payload.player_id,
                       topics=json.dumps(payload.topics, ensure_ascii=False), participants=json.dumps(payload.participants,ensure_ascii=False), demo=payload.demo)
        if payload.demo:
            g.pack, g.status = json.dumps(validate_pack({'clues':party_demo(demo_pack())},8) if payload.participants else demo_pack(), ensure_ascii=False), 'ready'
        elif payload.presentation:
            try:
                pack,meta=presentation_pack(payload.topics,payload.reserve)
            except ValueError as error:
                raise HTTPException(422,str(error)) from None
            g.pack,g.status,g.presentation_meta=json.dumps(pack,ensure_ascii=False),'ready',json.dumps(meta,ensure_ascii=False)
        db.add(g)
        db.flush()
        result = view(g)
        db.commit()
        if not payload.demo and not payload.presentation:
            tasks.add_task(generate, g.id)
        return result

    @app.get('/api/trivia/games/{sid}')
    def get(sid: str, db: Session = Depends(db_session)):
        return view(require(db, sid))

    @app.get('/api/trivia/games/{sid}/host-sheet')
    def host_sheet(sid: str, response: Response, db: Session = Depends(db_session)):
        g=require(db,sid)
        if g.status not in {'ready','finished'}:
            raise HTTPException(409,'Ответы появятся после подготовки вопросов')
        response.headers['Cache-Control']='no-store'
        topics=json.loads(g.topics)
        clues=json.loads(g.pack)
        return dict(id=g.id,topics=[dict(name=topic,questions=[dict(
            cell=i,price=q['price'],question=q['question'],answer=q['answer'],
            aliases=q['aliases'],explanation=q['explanation'],options=q.get('options',[]),
            host_review=bool(notes_for(g,i)),review_note=' '.join(n['reason'] for n in notes_for(g,i)))
            for i,q in enumerate(clues) if q['topic_index']==t]) for t,topic in enumerate(topics)])

    @app.post('/api/trivia/games/{sid}/open')
    def open_cell(sid: str, payload: CellInput, db: Session = Depends(db_session)):
        db.execute(text('BEGIN IMMEDIATE'))
        g = require(db, sid)
        if g.status != 'ready':
            raise HTTPException(409, 'Поле пока недоступно')
        if payload.cell >= len(json.loads(g.pack)):
            raise HTTPException(422,'Клетка вне поля')
        if g.pending:
            if json.loads(g.pending)['cell'] == payload.cell:
                return view(g)
            raise HTTPException(409, 'Сначала завершите текущий вопрос')
        if any(r['cell'] == payload.cell for r in json.loads(g.results)):
            raise HTTPException(409, 'Этот вопрос уже сыгран')
        names=json.loads(g.participants or '[]')
        g.pending = json.dumps(dict(cell=payload.cell, participant=len(json.loads(g.results)) % len(names) if names else 0, deadline=clock()+60, time_limit=60, paused=False, submitted=None,
                                    grading=False, grade_error=''))
        db.commit()
        return view(g)

    def audience_timer(sid,payload,db,pause):
        db.execute(text('BEGIN IMMEDIATE'))
        g=require(db,sid)
        pending=json.loads(g.pending) if g.pending else None
        if g.status!='ready' or not pending or pending['cell']!=payload.cell or pending['submitted'] is not None:
            raise HTTPException(409,'Помощь зала доступна только во время ответа')
        if pause and not pending.get('paused'):
            now=clock()
            if now>=pending['deadline']:
                settle(db,g,pending,'timeout')
                return view(g)
            pending.update(paused=True,remaining=pending['deadline']-now)
        elif not pause and pending.get('paused'):
            pending.update(paused=False,deadline=clock()+pending.pop('remaining'))
        g.pending=json.dumps(pending,ensure_ascii=False)
        db.commit()
        return view(g)

    @app.post('/api/trivia/games/{sid}/audience-help')
    def audience_help(sid:str,payload:CellInput,db:Session=Depends(db_session)):
        return audience_timer(sid,payload,db,True)

    @app.post('/api/trivia/games/{sid}/resume-answer')
    def resume_answer(sid:str,payload:CellInput,db:Session=Depends(db_session)):
        return audience_timer(sid,payload,db,False)

    @app.post('/api/trivia/games/{sid}/answer')
    def answer(sid: str, payload: FreeAnswer, tasks: BackgroundTasks, db: Session = Depends(db_session)):
        db.execute(text('BEGIN IMMEDIATE'))
        g = require(db, sid)
        if any(r['cell'] == payload.cell for r in json.loads(g.results)):
            return view(g)
        pending = json.loads(g.pending) if g.pending else None
        if not pending or pending['cell'] != payload.cell:
            raise HTTPException(409, 'Откройте вопрос перед ответом')
        if pending.get('manual'):
            return view(g)
        if pending['grading'] and clock()-pending.get('started', clock()) < 100:
            return view(g)
        if pending['submitted'] is None:
            if pending.get('paused') and not payload.skip:
                raise HTTPException(409,'Помощь зала: сначала продолжите ответ')
            if not pending.get('paused') and clock() >= pending['deadline']:
                settle(db, g, pending, 'timeout')
                return view(g)
            if payload.skip:
                settle(db, g, pending, 'skip')
                return view(g)
            value = (payload.answer or '').strip()
            if not value:
                raise HTTPException(422, 'Сначала произнесите или введите ответ')
            clue = json.loads(g.pack)[payload.cell]
            if clue.get('kind') in {'choice','yesno'} and value not in clue['options']:
                raise HTTPException(422,'Выберите один из четырёх вариантов')
            pending['submitted'] = value
        clue = json.loads(g.pack)[payload.cell]
        is_choice=clue.get('kind') in {'choice','yesno'}
        correct=pending['submitted']==clue['answer'] if is_choice else exact_answer(pending['submitted'], clue)
        if notes_for(g,payload.cell):
            pending.update(manual=True,grading=False,grade_error='')
            g.pending=json.dumps(pending,ensure_ascii=False)
            db.commit()
        elif correct:
            settle(db, g, pending, 'correct')
        elif g.presentation_meta and not is_choice:
            pending.update(manual=True,grading=False,grade_error='')
            g.pending=json.dumps(pending,ensure_ascii=False)
            db.commit()
        elif g.demo or is_choice:
            reason='Выбран неверный вариант ответа.' if is_choice else 'В деморежиме проверяются только точные ответы и подготовленные варианты.'
            settle(db, g, pending, 'incorrect', reason)
        else:
            pending.update(grading=True, grade_error='', token=str(uuid4()), started=clock())
            g.pending = json.dumps(pending, ensure_ascii=False)
            db.commit()
            tasks.add_task(grade, sid, pending['token'])
        return view(g)

    @app.post('/api/trivia/games/{sid}/judge')
    def judge(sid: str,payload: HostVerdict,db: Session = Depends(db_session)):
        db.execute(text('BEGIN IMMEDIATE'))
        g=require(db,sid)
        if not g.presentation_meta and not notes_for(g,payload.cell):
            raise HTTPException(409,'Для этой клетки не назначена оценка ведущего')
        if any(r['cell']==payload.cell for r in json.loads(g.results)):
            return view(g)
        pending=json.loads(g.pending) if g.pending else None
        if not pending or pending['cell']!=payload.cell or not pending.get('manual') or pending['submitted'] is None:
            raise HTTPException(409,'Сначала зафиксируйте свободный ответ')
        settle(db,g,pending,payload.decision,'Решение ведущего.')
        return view(g)

    @app.post('/api/trivia/games/{sid}/use-draft')
    def use_draft(sid:str,db:Session=Depends(db_session)):
        db.execute(text('BEGIN IMMEDIATE'))
        g=require(db,sid)
        if not has_playable_draft(g):
            raise HTTPException(409,'Готового поля из 40 вопросов пока нет')
        clues=validate_pack({'clues':json.loads(g.pack)},8)
        g.pack=json.dumps(clues,ensure_ascii=False)
        g.editorial_notes=json.dumps([dict(topic_index=q['topic_index'],price=q['price'],reason='Сохранённый набор: решение принимает ведущий.') for q in clues],ensure_ascii=False)
        g.status,g.error='ready',''
        db.commit()
        return view(g)

    @app.post('/api/trivia/games/{sid}/finish')
    def finish(sid: str, db: Session = Depends(db_session)):
        db.execute(text('BEGIN IMMEDIATE'))
        g = require(db, sid)
        if g.status == 'generating':
            raise HTTPException(409, 'Дождитесь окончания подготовки')
        if g.pending and json.loads(g.pending)['submitted'] is not None:
            raise HTTPException(409, 'Сначала завершите проверку зафиксированного ответа')
        if g.pending:
            settle(db, g, json.loads(g.pending), 'skip')
        g.status = 'finished'
        db.commit()
        return view(g)
