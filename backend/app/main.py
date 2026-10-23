import json
import os
import random
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Integer, create_engine, event, func, select, text
from sqlalchemy.orm import Session

from .adaptive import CATEGORIES, Knowledge, category_weights, choose_question, difficulty_for, level_for, level_name, xp_for
from .models import Achievement, Answer, Base, GameSession, Player, PlayerAchievement, Question, now
from .questions import question_rows

ACHIEVEMENTS = [
    ('first', 'Первый шаг', 'Первый правильный ответ'),
    ('perfect', 'Без ошибок', 'Все 10 ответов в завершённом раунде верны'),
    ('streak', 'Серия побед', 'Пять правильных ответов подряд в одном раунде'),
    ('math', 'Математик', 'Точность по математике не ниже 80% при 10 ответах'),
    ('code', 'Программист', 'Точность по программированию не ниже 80% при 10 ответах'),
    ('scholar', 'Эрудит', 'Точность не ниже 70% в трёх категориях, минимум 6 ответов в каждой'),
]


class PlayerInput(BaseModel):
    nickname: str = Field(min_length=1, max_length=40)


class StartInput(BaseModel):
    player_id: int = Field(gt=0)


class AnswerInput(BaseModel):
    question_id: int = Field(gt=0)
    selected: int | None = Field(default=None, ge=0, le=3)


def create_app(database_url=None, rng=None, clock=None, quiz_provider=None):
    current_time = clock or time.time
    url = database_url or os.getenv('DATABASE_URL') or f"sqlite:///{Path(__file__).resolve().parent.parent / 'battle.db'}"
    engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 30})

    @event.listens_for(engine, 'connect')
    def enable_fk(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')

    def initialize():
        Base.metadata.create_all(engine)
        # Preserve existing local profiles when upgrading databases created before timers.
        with engine.begin() as connection:
            connection.execute(text('BEGIN IMMEDIATE'))
            columns = {row[1] for row in connection.execute(text('PRAGMA table_info(game_sessions)'))}
            if 'deadline_at' not in columns:
                connection.execute(text('ALTER TABLE game_sessions ADD COLUMN deadline_at FLOAT'))
            trivia_columns = {row[1] for row in connection.execute(text('PRAGMA table_info(trivia_games)'))}
            if 'participants' not in trivia_columns:
                connection.execute(text("ALTER TABLE trivia_games ADD COLUMN participants TEXT NOT NULL DEFAULT '[]'"))
            if 'presentation_meta' not in trivia_columns:
                connection.execute(text("ALTER TABLE trivia_games ADD COLUMN presentation_meta TEXT NOT NULL DEFAULT ''"))
            if 'editorial_notes' not in trivia_columns:
                connection.execute(text("ALTER TABLE trivia_games ADD COLUMN editorial_notes TEXT NOT NULL DEFAULT '[]'"))
        with Session(engine) as db:
            db.execute(text('BEGIN IMMEDIATE'))
            for data in question_rows():
                if not db.get(Question, data['id']):
                    db.add(Question(**data))
            for aid, name, description in ACHIEVEMENTS:
                if not db.get(Achievement, aid):
                    db.add(Achievement(id=aid, name=name, description=description))
            db.commit()

        app.state.recover_trivia_jobs()

    @asynccontextmanager
    async def lifespan(_):
        initialize()
        yield
        engine.dispose()

    app = FastAPI(title='AI Knowledge Battle', lifespan=lifespan)
    app.state.engine = engine
    app.state.initialize = initialize
    random_source = rng or random.Random()
    app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                       allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])

    def get_db():
        with Session(engine) as db:
            yield db

    def require(db, model, ident):
        obj = db.get(model, ident)
        if obj is None:
            raise HTTPException(404, 'Игрок или сессия не найдены')
        return obj

    def profile(p):
        level = level_for(p.xp)
        return dict(id=p.id, nickname=p.nickname, xp=p.xp, level=level, title=level_name(level),
                    level_progress=p.xp % 100, next_level_xp=level * 100)

    def knowledge(db, pid, sid=None):
        query = select(Question.category, func.count(Answer.id), func.sum(Answer.is_correct.cast(Integer))).join(Answer, Answer.question_id == Question.id).where(Answer.player_id == pid)
        if sid:
            query = query.where(Answer.session_id == sid)
        stats = {c: Knowledge(int(n), int(k or 0)) for c, n, k in db.execute(query.group_by(Question.category))}
        return {c: stats.get(c, Knowledge()) for c in CATEGORIES}

    def analytics(stats):
        weights = category_weights(stats)
        return [dict(category=c, attempts=k.attempts, correct=k.correct,
                     accuracy=round(k.correct / k.attempts * 100, 1) if k.attempts else None,
                     mastery=round(k.mastery * 100, 1), next_difficulty=difficulty_for(k),
                     probability=round(weights[c] * 100, 1)) for c, k in stats.items()]

    def award(db, game, perfect=False):
        stats = knowledge(db, game.player_id)
        eligible = set()
        if any(k.correct for k in stats.values()): eligible.add('first')
        if game.streak >= 5: eligible.add('streak')
        if perfect: eligible.add('perfect')
        for c, aid in [('Математика', 'math'), ('Программирование', 'code')]:
            k = stats[c]
            if k.attempts >= 10 and k.correct / k.attempts >= .8: eligible.add(aid)
        if sum(k.attempts >= 6 and k.correct / k.attempts >= .7 for k in stats.values()) >= 3:
            eligible.add('scholar')
        owned = set(db.scalars(select(PlayerAchievement.achievement_id).where(PlayerAchievement.player_id == game.player_id)))
        for aid in eligible - owned:
            db.add(PlayerAchievement(player_id=game.player_id, achievement_id=aid, session_id=game.id))
        db.flush()
        return sorted(eligible - owned)

    def answer_view(db, answer):
        q = db.get(Question, answer.question_id)
        return dict(question_id=q.id, question=q.text, category=q.category, selected=None if answer.selected == -1 else answer.selected,
                    timed_out=answer.selected == -1,
                    correct=q.correct, is_correct=answer.is_correct, xp=answer.xp,
                    explanation=q.explanation, options=json.loads(q.options), created_at=answer.created_at)

    def session_view(db, g):
        answers = list(db.scalars(select(Answer).where(Answer.session_id == g.id).order_by(Answer.id)))
        correct = sum(a.is_correct for a in answers)
        stats = analytics(knowledge(db, g.player_id, g.id))
        strong = [s['category'] for s in stats if s['attempts'] >= 2 and s['mastery'] >= 60]
        weak = [s['category'] for s in stats if s['attempts'] >= 2 and s['mastery'] < 50]
        earned = list(db.scalars(select(Achievement.name).join(PlayerAchievement).where(PlayerAchievement.session_id == g.id)))
        return dict(id=g.id, player_id=g.player_id, total=g.total, answered=len(answers), correct=correct,
                    wrong=len(answers)-correct, accuracy=round(correct/len(answers)*100) if answers else 0,
                    xp=g.xp, streak=g.streak, finished=bool(g.finished_at),
                    initial_level=level_for(g.start_xp), current_level=level_for(db.get(Player, g.player_id).xp),
                    achievements=earned, strong=strong, weak=weak, categories=stats,
                    recommendation=('Практикуйте: ' + ', '.join(weak)) if weak else 'Продолжайте раунд: больше ответов уточнят оценку знаний.',
                    last_answer=answer_view(db, answers[-1]) if answers else None,
                    pending_id=g.pending_id)

    @app.get('/api/health')
    def health(): return {'status': 'ok'}

    @app.post('/api/players')
    def player_create(payload: PlayerInput, db: Session = Depends(get_db)):
        nickname = ' '.join(payload.nickname.split())
        if not nickname: raise HTTPException(422, 'Введите никнейм')
        db.execute(text('BEGIN IMMEDIATE'))
        p = db.scalar(select(Player).where(Player.nickname == nickname))
        if not p:
            p = Player(nickname=nickname)
            db.add(p)
            db.flush()
        result = profile(p)
        db.commit()
        return result

    @app.get('/api/players/{pid}')
    def player_get(pid: int, db: Session = Depends(get_db)):
        return profile(require(db, Player, pid))

    @app.get('/api/players/{pid}/stats')
    def stats_get(pid: int, db: Session = Depends(get_db)):
        p = require(db, Player, pid)
        history = list(db.scalars(select(Answer).where(Answer.player_id == pid).order_by(Answer.id.desc()).limit(100)))
        games = db.scalar(select(func.count()).select_from(GameSession).where(GameSession.player_id == pid, GameSession.finished_at.is_not(None)))
        active = db.scalar(select(GameSession.id).where(GameSession.player_id == pid, GameSession.finished_at.is_(None)))
        return dict(player=profile(p), games=games, categories=analytics(knowledge(db, pid)),
                    history=[answer_view(db, a) for a in history], active_session=active)

    @app.get('/api/players/{pid}/achievements')
    def achievements_get(pid: int, db: Session = Depends(get_db)):
        require(db, Player, pid)
        owned = {a.achievement_id: a.earned_at for a in db.scalars(select(PlayerAchievement).where(PlayerAchievement.player_id == pid))}
        return [dict(id=a.id, name=a.name, description=a.description, earned_at=owned.get(a.id)) for a in db.scalars(select(Achievement))]

    @app.post('/api/sessions')
    def start(payload: StartInput, db: Session = Depends(get_db)):
        db.execute(text('BEGIN IMMEDIATE'))
        p = require(db, Player, payload.player_id)
        game = db.scalar(select(GameSession).where(GameSession.player_id == p.id, GameSession.finished_at.is_(None)))
        if not game:
            game = GameSession(id=str(uuid4()), player_id=p.id, start_xp=p.xp)
            db.add(game)
            db.flush()
        result = session_view(db, game)
        db.commit()
        return result

    @app.get('/api/sessions/{sid}')
    def get_game(sid: str, db: Session = Depends(get_db)):
        return session_view(db, require(db, GameSession, sid))

    @app.post('/api/sessions/{sid}/next')
    def next_question(sid: str, db: Session = Depends(get_db)):
        db.execute(text('BEGIN IMMEDIATE'))
        game = require(db, GameSession, sid)
        if game.finished_at: raise HTTPException(409, 'Раунд уже завершён')
        seen = json.loads(game.issued)
        if game.pending_id:
            q = db.get(Question, game.pending_id)
        else:
            if len(seen) >= game.total: raise HTTPException(409, 'Все вопросы пройдены. Завершите раунд.')
            q = choose_question(list(db.scalars(select(Question))), seen, knowledge(db, game.player_id), random_source)
            if q is None: raise HTTPException(409, 'Новые вопросы закончились. Завершите раунд.')
            game.pending_id = q.id
            seen.append(q.id)
            game.issued = json.dumps(seen)
        if game.deadline_at is None:
            game.deadline_at = current_time() + 30
        result = dict(id=q.id, category=q.category, difficulty=q.difficulty, text=q.text,
                      options=json.loads(q.options), number=len(seen), total=game.total,
                      deadline_at=game.deadline_at, server_time=current_time(), time_limit=30)
        db.commit()
        return result

    @app.post('/api/sessions/{sid}/answers')
    def submit(sid: str, payload: AnswerInput, db: Session = Depends(get_db)):
        # SQLite write lock serializes answer verification, XP and awards as one transaction.
        db.execute(text('BEGIN IMMEDIATE'))
        g = require(db, GameSession, sid)
        if g.finished_at: raise HTTPException(409, 'Раунд уже завершён')
        if db.scalar(select(Answer).where(Answer.session_id == sid, Answer.question_id == payload.question_id)):
            raise HTTPException(409, 'Ответ на этот вопрос уже подтверждён')
        if g.pending_id != payload.question_id: raise HTTPException(409, 'Вопрос не назначен этой сессии')
        q = db.get(Question, payload.question_id)
        if g.deadline_at is None:
            g.deadline_at = current_time() + 30
        expired = current_time() >= g.deadline_at
        if payload.selected is None and not expired:
            raise HTTPException(409, 'Время на ответ ещё не истекло')
        selected = -1 if expired else payload.selected
        correct = selected == q.correct
        g.streak = g.streak + 1 if correct else 0
        gained = xp_for(q.difficulty, correct, g.streak)
        p = db.get(Player, g.player_id)
        p.xp += gained
        g.xp += gained
        g.pending_id = None
        g.deadline_at = None
        answer = Answer(session_id=sid, player_id=p.id, question_id=q.id, selected=selected, is_correct=correct, xp=gained)
        db.add(answer)
        db.flush()
        earned = award(db, g)
        result = dict(answer=answer_view(db, answer), session=session_view(db, g), player=profile(p), new_achievements=earned)
        db.commit()
        return result

    @app.post('/api/sessions/{sid}/finish')
    def finish(sid: str, db: Session = Depends(get_db)):
        db.execute(text('BEGIN IMMEDIATE'))
        g = require(db, GameSession, sid)
        if not g.finished_at:
            if g.pending_id and g.deadline_at is not None and current_time() >= g.deadline_at:
                db.add(Answer(session_id=sid, player_id=g.player_id, question_id=g.pending_id, selected=-1, is_correct=False, xp=0))
                g.streak = 0
                db.flush()
            count = db.scalar(select(func.count()).select_from(Answer).where(Answer.session_id == sid))
            correct = db.scalar(select(func.count()).select_from(Answer).where(Answer.session_id == sid, Answer.is_correct.is_(True)))
            g.finished_at = now()
            g.pending_id = None
            g.deadline_at = None
            award(db, g, perfect=count == g.total and correct == g.total)
        result = session_view(db, g)
        db.commit()
        return result

    from .trivia import register_trivia
    register_trivia(app, engine, current_time, quiz_provider)
    return app


app = create_app()
