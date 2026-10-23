"""Vetted local illustrations; no model-supplied URLs or executable SVG."""
import random

IMAGE_CATALOG = {
    'japan': {'description':'Флаг: белое прямоугольное поле и красный круг по центру.', 'tags':['географ','флаг','стран','япони','истори']},
    'brazil': {'description':'Флаг Бразилии: зелёное поле, жёлтый ромб, синий круг со звёздами и белой лентой.', 'tags':['географ','флаг','бразил','стран']},
    'triangle': {'description':'Прямоугольный треугольник ABC: AB=3, BC=4, прямой угол B. Длина AC не подписана.', 'tags':['математ','геометр','алгебр','школ']},
    'orbit': {'description':'Схема затмения: Солнце слева, Луна посередине, Земля справа. Лучи Солнца и тень Луны падают на Землю.', 'tags':['космос','астроном','наук','физик']},
    'knight': {'description':'Шахматная доска 8x8. Конь находится на d4. Других фигур нет. Видны обозначения a–h, 1–8.', 'tags':['шахмат','спорт','логик','загад']},
    'court': {'description':'Схематичная баскетбольная площадка сверху с двумя кольцами, центральным кругом, дугами трёхочковых и прямоугольными ограниченными зонами. Игрок А отмечен синим кругом вне трёхочковой дуги левого кольца, игрок Б — красным внутри левой ограниченной зоны. Подпись: «Броски в левое кольцо».', 'tags':['баскет','спорт','нба','nba']},
    'cat': {'description':'Оригинальная иллюстрация: спокойный кот с чашкой чая сидит за столом в комнате с огнём. Это визуальная загадка-отсылка, не оригинальный кадр мема.', 'tags':['мем','интернет','юмор']},
    'frames': {'description':'Три последовательных кадра: мяч слева, по центру, справа; на каждом кадре он чуть выше. Стрелка показывает воспроизведение слева направо.', 'tags':['кино','анимац','мульт','фильм','программ','python']},
}


def image_url(image_id):
    return f'/quiz-images/{image_id}.svg' if image_id in IMAGE_CATALOG else None


def format_plan(topics, rng=None):
    rng = rng or random.SystemRandom()
    plan = []
    for t, topic in enumerate(topics):
        eligible = [key for key, value in IMAGE_CATALOG.items()
                    if any(tag in topic.casefold() for tag in value['tags'])]
        kinds = ['open', 'open', 'riddle', 'choice', 'image' if eligible else 'choice']
        rng.shuffle(kinds)
        # The small illustration library is suited to recognition and simple inference.
        # Do not inflate a simple picture into an unfair 500-point question.
        if 'image' in kinds and kinds.index('image') > 2:
            index, target = kinds.index('image'), rng.randrange(3)
            kinds[index], kinds[target] = kinds[target], kinds[index]
        for index, kind in enumerate(kinds):
            plan.append(dict(topic_index=t, price=(index+1)*100, kind=kind,
                             image_id=rng.choice(eligible) if kind == 'image' else ''))
    return plan


def validate_mixed(clues, plan=None, expected_count=40):
    if len(clues) != expected_count:
        raise ValueError(f'Нужны {expected_count} вопросов')
    slots = {(p['topic_index'], p['price']):p for p in plan} if plan else {}
    for q in clues:
        kind = q.get('kind')
        if kind not in {'open','riddle','choice','image'}:
            raise ValueError('Неизвестный формат')
        if plan:
            slot = slots.get((q['topic_index'],q['price']))
            if not slot or any(q[k] != slot[k] for k in ('kind','image_id')):
                raise ValueError('Модель изменила назначенный формат')
        options = q.get('options',[])
        if kind == 'choice':
            if len(options) != 4 or any(not isinstance(v,str) or not v.strip() or len(v)>160 for v in options):
                raise ValueError('Нужны четыре коротких варианта')
            if len({v.strip().casefold() for v in options}) != 4:
                raise ValueError('Варианты должны различаться и включать эталон')
            # Match generated reference wording to the actual button text. Only
            # case and surrounding whitespace are ignored, never aliases/code punctuation.
            canonical = next((v for v in options if v.strip().casefold()==q['answer'].strip().casefold()),None)
            if canonical is None:
                raise ValueError('Варианты должны различаться и включать эталон')
            q['answer'] = canonical
        elif options:
            raise ValueError('Варианты допустимы только для choice')
        if kind == 'image':
            if q.get('image_id') not in IMAGE_CATALOG:
                raise ValueError('Неизвестная иллюстрация')
        elif q.get('image_id'):
            raise ValueError('Иллюстрация допустима только для image')
    return clues
