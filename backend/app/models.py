from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = 'players'
    id: Mapped[int] = mapped_column(primary_key=True)
    nickname: Mapped[str] = mapped_column(String(40), unique=True)
    xp: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[str] = mapped_column(default=now)


class Question(Base):
    __tablename__ = 'questions'
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str]
    difficulty: Mapped[str]
    text: Mapped[str] = mapped_column(Text, unique=True)
    options: Mapped[str] = mapped_column(Text)
    correct: Mapped[int]
    explanation: Mapped[str] = mapped_column(Text)


class GameSession(Base):
    __tablename__ = 'game_sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'))
    total: Mapped[int] = mapped_column(default=10)
    issued: Mapped[str] = mapped_column(Text, default='[]')
    pending_id: Mapped[int | None] = mapped_column(ForeignKey('questions.id'), nullable=True)
    deadline_at: Mapped[float | None] = mapped_column(nullable=True)
    xp: Mapped[int] = mapped_column(default=0)
    streak: Mapped[int] = mapped_column(default=0)
    start_xp: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[str] = mapped_column(default=now)
    finished_at: Mapped[str | None] = mapped_column(nullable=True)


class Answer(Base):
    __tablename__ = 'answers'
    __table_args__ = (UniqueConstraint('session_id', 'question_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('game_sessions.id'))
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'))
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id'))
    selected: Mapped[int]
    is_correct: Mapped[bool]
    xp: Mapped[int]
    created_at: Mapped[str] = mapped_column(default=now)


class Achievement(Base):
    __tablename__ = 'achievements'
    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str]


class PlayerAchievement(Base):
    __tablename__ = 'player_achievements'
    __table_args__ = (UniqueConstraint('player_id', 'achievement_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'))
    achievement_id: Mapped[str] = mapped_column(ForeignKey('achievements.id'))
    session_id: Mapped[str] = mapped_column(ForeignKey('game_sessions.id'))
    earned_at: Mapped[str] = mapped_column(default=now)


class TriviaGame(Base):
    __tablename__ = 'trivia_games'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    player_id: Mapped[int] = mapped_column(ForeignKey('players.id'))
    participants: Mapped[str] = mapped_column(Text, default='[]')
    topics: Mapped[str] = mapped_column(Text)
    pack: Mapped[str] = mapped_column(Text, default='[]')
    results: Mapped[str] = mapped_column(Text, default='[]')
    pending: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(default='generating')
    demo: Mapped[bool] = mapped_column(default=False)
    presentation_meta: Mapped[str] = mapped_column(Text, default='')
    editorial_notes: Mapped[str] = mapped_column(Text, default='[]')
    error: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[str] = mapped_column(default=now)
