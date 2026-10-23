"""Explainable rules, not a trained ML model. All functions are storage-independent."""
from dataclasses import dataclass
import random

CATEGORIES = ('Программирование', 'Математика', 'История', 'География', 'Наука')
DIFFICULTIES = ('easy', 'medium', 'hard')


@dataclass(frozen=True)
class Knowledge:
    attempts: int = 0
    correct: int = 0

    @property
    def mastery(self):
        return (self.correct + 1) / (self.attempts + 2)


def difficulty_for(k: Knowledge) -> str:
    if k.attempts < 4:
        return 'medium'
    if k.mastery < .45:
        return 'easy'
    if k.mastery >= .75:
        return 'hard'
    return 'medium'


def category_weights(stats):
    # 30% uniform exploration plus 70% practice weighted by uncertainty/errors.
    raw = {c: 1 - stats.get(c, Knowledge()).mastery for c in CATEGORIES}
    total = sum(raw.values())
    return {c: .3 / len(CATEGORIES) + .7 * raw[c] / total for c in CATEGORIES}


def choose_question(questions, seen, stats, rng=None):
    rng = rng or random.Random()
    available = [q for q in questions if q.id not in seen]
    if not available:
        return None
    categories = [c for c in CATEGORIES if any(q.category == c for q in available)]
    weights = category_weights(stats)
    category = rng.choices(categories, weights=[weights[c] for c in categories], k=1)[0]
    target = difficulty_for(stats.get(category, Knowledge()))
    pool = [q for q in available if q.category == category]
    distance = min(abs(DIFFICULTIES.index(q.difficulty) - DIFFICULTIES.index(target)) for q in pool)
    return rng.choice([q for q in pool if abs(DIFFICULTIES.index(q.difficulty) - DIFFICULTIES.index(target)) == distance])


def level_for(xp):
    return 1 + xp // 100


def level_name(level):
    names = ['Новичок', 'Ученик', 'Исследователь', 'Стратег', 'Мастер знаний']
    return names[level - 1] if level <= 5 else f'Легенда знаний {level - 5}'


def xp_for(difficulty, correct, streak):
    return ({'easy': 10, 'medium': 20, 'hard': 30}[difficulty] + (30 if streak % 5 == 0 else 0)) if correct else 0
