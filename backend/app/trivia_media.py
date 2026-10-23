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


# Descriptions/references are server-only generation context. Public media has neutral filenames.
MEDIA_CATALOG = {
 's01':dict(kind='image',url='/quiz-media/s01.jpg',series=True,reference='Игра в кальмара',description='Кадр: мужчина в тёмной одежде сидит в кожаном кресле; это Фронтмен из «Игры в кальмара». Спрашивай только сериал, не имя актёра.',tags=['сериал','кино'],credit='No Ju-han / Netflix',source='https://www.netflix.com/tudum/galleries/squid-game-season-2-photo-gallery'),
 's02':dict(kind='image',url='/quiz-media/s02.jpg',series=True,reference='Ван-Пис',description='Кадр игрового сериала ONE PIECE: команда на деревянной палубе, Луффи в соломенной шляпе. Спрашивай название сериала.',tags=['сериал','кино'],credit='Netflix / Tudum',source='https://www.netflix.com/tudum/galleries/one-piece-first-look-photos'),
 's03':dict(kind='image',url='/quiz-media/s03.jpg',series=True,reference='Уэнсдэй',description='Кадр: Уэнсдэй Аддамс с косами сидит за столом с пишущей машинкой. Спрашивай сериал «Уэнсдэй».',tags=['сериал','кино'],credit='Netflix / Tudum',source='https://www.netflix.com/tudum/wednesday'),
 's04':dict(kind='image',url='/quiz-media/s04.jpg',series=True,reference='Очень странные дела',description='Кадр: Одиннадцать с короткими волосами в серой одежде в синем пространстве с красными частицами. Сериал «Очень странные дела».',tags=['сериал','кино'],credit='Netflix / Tudum',source='https://www.netflix.com/tudum/stranger-things'),
 's05':dict(kind='image',url='/quiz-media/s05.jpg',series=True,reference='Ведьмак',description='Кадр: Геральт с длинными белыми волосами, исполненный Генри Кавиллом. Спрашивай сериал «Ведьмак».',tags=['сериал','кино'],credit='Netflix / Tudum',source='https://www.netflix.com/tudum/the-witcher'),
 'a01':dict(kind='audio',url='/quiz-media/a01.wav',description='Подлинная запись Нила Армстронга: One small step for (a) man, one giant leap for mankind. Оригинальная земная версия, не симуляция атмосферы Марса. Можно спросить говорящего или миссию Apollo 11.',tags=['космос','истори','аудио'],credit='NASA/JPL-Caltech',source='https://science.nasa.gov/resource/sounds-of-mars-one-small-step/'),
 'a02':dict(kind='audio',url='/quiz-media/a02.wav',description='Авторская запись азбуки Морзе: три коротких, три длинных, три коротких сигнала. Ответ SOS; это не запись телепередачи.',tags=['звук','аудио','морзе','связь'],credit='AI Knowledge Battle — собственная запись',source=''),
 'a03':dict(kind='audio',url='/quiz-media/a03.wav',description='Авторская запись двух чистых тонов 440 и 880 Гц: второй выше первого на октаву, частота удвоилась. Можно спросить интервал или отношение частот.',tags=['музык','звук','аудио','наук','физик'],credit='AI Knowledge Battle — собственная запись',source=''),
 'a04':dict(kind='audio',url='/quiz-media/a04.wav',description='Авторская запись: до, ми, соль по очереди в восходящем порядке, повторено дважды. Это звуки до-мажорного трезвучия. Не выдавай за известную песню.',tags=['музык','звук','аудио'],credit='AI Knowledge Battle — собственная запись',source=''),
 'v01':dict(kind='video',url='/quiz-media/v01.mp4',description='12 секунд подлинной съёмки Apollo 15: Дэвид Скотт выпускает молоток и перо на Луне, они достигают поверхности практически одновременно. Видео без звука. Можно спросить причину: практически нет сопротивления воздуха.',tags=['космос','наук','физик','видео'],credit='NASA — Apollo 15',source='https://science.nasa.gov/resource/the-apollo-15-hammer-feather-drop/'),
 'v02':dict(kind='video',url='/quiz-media/v02.mp4',description='Авторская анимация маятника: груз колеблется на нити, совершая полный цикл за 2 секунды; ролик 6 секунд, три полных периода. Это схема, не запись лабораторного эксперимента.',tags=['наук','физик','математ','видео'],credit='AI Knowledge Battle — собственная анимация',source=''),
 'v03':dict(kind='video',url='/quiz-media/v03.mp4',description='Авторская анимация мяча: он движется вправо и трижды подскакивает над горизонтальной линией. Это схема, не съёмка спортивного матча.',tags=['математ','физик','видео'],credit='AI Knowledge Battle — собственная анимация',source=''),
}
SPECIAL_TOPICS = ['Кадры из сериалов','Химическая (или бытовая) загадка','Да или Нет']


def topic_style(topic):
    value=' '.join(topic.casefold().replace('ё','е').split())
    if ('сериал' in value and any(w in value for w in ('кадр','угадай','размыт','пиксел','силуэт'))):
        return 'frames'
    if value in {'да или нет','да/нет','да нет'}:
        return 'yesno'
    if 'загад' in value and any(w in value for w in ('хим','бытов')):
        return 'linked'
    return ''


def public_media(clue, reveal=False):
    asset=MEDIA_CATALOG.get(clue.get('image_id',''))
    if not asset:
        return None
    result=dict(kind=asset['kind'],url=asset['url'],mask='none',level=clue['price']//100)
    if asset.get('series') and not reveal:
        result['mask']='pixel' if clue['price'] in (200,400) else 'blur'
    if reveal:
        result.update(credit=asset['credit'],source=asset['source'])
    return result


def format_plan(topics, rng=None):
    rng = rng or random.SystemRandom()
    plan = []
    used_media=set()
    for t, topic in enumerate(topics):
        style=topic_style(topic)
        if style=='frames':
            ids=[key for key,value in MEDIA_CATALOG.items() if value.get('series')]
            rng.shuffle(ids)
            plan.extend(dict(topic_index=t,price=(i+1)*100,kind='image',image_id=key) for i,key in enumerate(ids[:5]))
            continue
        if style in {'yesno','linked'}:
            plan.extend(dict(topic_index=t,price=p,kind=style,image_id='') for p in range(100,501,100))
            continue
        eligible = [key for key, value in IMAGE_CATALOG.items()
                    if any(tag in topic.casefold() for tag in value['tags'])]
        dynamic=[(key,v) for key,v in MEDIA_CATALOG.items() if key not in used_media and not v.get('series') and any(tag in topic.casefold() for tag in v['tags'])]
        audio=[key for key,v in dynamic if v['kind']=='audio']
        video=[key for key,v in dynamic if v['kind']=='video']
        kinds=['open','riddle','choice','audio' if audio else 'open','video' if video else 'image' if eligible else 'choice']
        rng.shuffle(kinds)
        # Recognition/counting clips suit 100–300; advanced slots retain knowledge questions.
        for media_kind in ('image','audio','video'):
            if media_kind in kinds and kinds.index(media_kind)>2:
                index=kinds.index(media_kind)
                target=rng.choice([i for i in range(3) if kinds[i] not in {'image','audio','video'}])
                kinds[index],kinds[target]=kinds[target],kinds[index]
        for i,kind in enumerate(kinds):
            key=rng.choice(audio) if kind=='audio' else rng.choice(video) if kind=='video' else rng.choice(eligible) if kind=='image' else ''
            if kind in {'audio','video'}:
                used_media.add(key)
            plan.append(dict(topic_index=t,price=(i+1)*100,kind=kind,image_id=key))
    return plan


def generation_catalog(plan=None):
    catalog={**IMAGE_CATALOG,**MEDIA_CATALOG}
    return catalog if plan is None else {p['image_id']:catalog[p['image_id']] for p in plan if p['image_id']}


MEDIA_RULES = """
Каждая клетка строго задана plan: topic_index, price, kind, image_id. Поле image_id
хранит ID зарегистрированного медиа и для аудио/видео. Не меняй назначенный материал.
open/riddle: options=[]. choice: четыре разных правдоподобных варианта,
один дословно равен answer. image/audio/video: options=[], вопрос требует
просмотра/прослушивания конкретного материала; используй только описание из images.
Не выдумывай слышимые слова, события, кадры, URL, HTML или SVG.
Схемы/собственные записи не называй кадрами фильмов или известной музыкой.
Для image с series=true спрашивай название сериала; эталон равен reference,
aliases включают русские и оригинальные названия. Не называй сериал, актёра,
имя персонажа или сюжетную подсказку в question: только формулировка задания
«Назовите сериал по размытому фрагменту №…». Не проси номер эпизода.
Для темы «Кадры из сериалов» сложность задают размытие/пиксели и кадрирование;
не отклоняй вопрос за простой текст, если ответ требует осмотра фрагмента.
yesno: options строго [«Да»,«Нет»], answer один из них. Формулируй утверждение
и спроси, верно ли оно. Используй научный/исторический парадокс с проверяемым
объяснением; никаких двойных отрицаний, опасных бытовых опытов и мифов за факты.
В пяти вопросах должны встречаться оба ответа; не делай все ответы «Нет».
linked: в question три коротких подсказки с метками 1), 2), 3).
Игрок называет ТРИ слова в том же порядке. В answer три слова через «;».
Все три содержат одну общую последовательность минимум из двух букв.
Закономерность НЕ сообщай в question; в explanation укажи три решения,
общий фрагмент и объясни каждую подсказку. Не требуй угадывать отсутствующее условие.
Пример принципа (не копировать дословно): растворитель для лака / материал
из цемента и заполнителей / плотная бумага для коробок. Решения: ацетон;
бетон; картон — общее «тон». Меняй наборы и связи, а не только порядок.
В остальных форматах image_id=''. Цена растёт по шкале знаний, а не длине текста.
"""


def validate_mixed(clues, plan=None, expected_count=40):
    if len(clues) != expected_count:
        raise ValueError(f'Нужны {expected_count} вопросов')
    slots = {(p['topic_index'], p['price']):p for p in plan} if plan else {}
    for q in clues:
        kind = q.get('kind')
        if kind not in {'open','riddle','choice','image','audio','video','yesno','linked'}:
            raise ValueError('Неизвестный формат')
        if plan:
            slot = slots.get((q['topic_index'],q['price']))
            if not slot or any(q[k] != slot[k] for k in ('kind','image_id')):
                raise ValueError('Модель изменила назначенный формат')
        options = q.get('options',[])
        if kind in {'choice','yesno'}:
            count=2 if kind=='yesno' else 4
            if kind=='yesno' and options!=['Да','Нет']:
                raise ValueError('Для Да или Нет нужны именно две кнопки')
            if len(options) != count or any(not isinstance(v,str) or not v.strip() or len(v)>160 for v in options):
                raise ValueError(f'Нужны {count} коротких варианта')
            if len({v.strip().casefold() for v in options}) != count:
                raise ValueError('Варианты должны различаться и включать эталон')
            # Match generated reference wording to the actual button text. Only
            # case and surrounding whitespace are ignored, never aliases/code punctuation.
            canonical = next((v for v in options if v.strip().casefold()==q['answer'].strip().casefold()),None)
            if canonical is None:
                raise ValueError('Варианты должны различаться и включать эталон')
            q['answer'] = canonical
        elif options:
            raise ValueError('Варианты допустимы только для choice/yesno')
        if kind in {'image','audio','video'}:
            asset=MEDIA_CATALOG.get(q.get('image_id'))
            if asset and asset['kind']!=kind:
                raise ValueError('Тип материала не совпадает с форматом')
            if not asset and (kind!='image' or q.get('image_id') not in IMAGE_CATALOG):
                raise ValueError('Неизвестная иллюстрация')
        elif q.get('image_id'):
            raise ValueError('Материал допустим только для image/audio/video')
        if kind=='linked':
            import re
            words=[re.sub(r'[^а-яa-z]', '', w.casefold().replace('ё','е')) for w in q['answer'].split(';')]
            if len(words)!=3 or any(not w for w in words) or not all(f'{i})' in q['question'] for i in (1,2,3)):
                raise ValueError('Нужны три подсказки и три ответа через точку с запятой')
            if not any(words[0][i:i+2] in words[1] and words[0][i:i+2] in words[2] for i in range(len(words[0])-1)):
                raise ValueError('В трёх решениях нет общего буквосочетания')
    return clues
