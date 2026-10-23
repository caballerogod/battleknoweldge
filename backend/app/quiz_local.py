"""Local-only Ollama provider. Never falls back to a paid provider."""
import json
import time
import threading
from typing import Literal
import httpx
from pydantic import ConfigDict, Field, create_model
from .quiz_ai import (OpenAIQuiz, Clue, MixedClue, Verdict, EditorialReview,
                      settings, validate_pack, normalize)
from .quiz_editor import RULES, obvious_issues
from .trivia_media import format_plan, IMAGE_CATALOG, validate_mixed
from .ai_usage import start_request, finish_local_request

URL = 'http://127.0.0.1:11434'
# One generation job at a time prevents CPU/RAM thrashing on a 16 GB laptop.
GENERATION_LOCK = threading.Lock()


def local_model():
    model = settings()['OLLAMA_MODEL'].strip()
    if not model or model.rsplit(':',1)[-1].endswith('cloud'):
        raise RuntimeError('Для бесплатного режима нужна локальная модель Ollama, без суффикса cloud.')
    return model


def cells_schema(index, slots, prices, mixed):
    """Const metadata prevents small models from swapping prices/formats."""
    fields = {}
    for price in prices:
        fixed = dict(topic_index=(Literal[index],...),price=(Literal[price],...))
        if mixed:
            slot = next(s for s in slots if s['price']==price)
            count = 4 if slot['kind']=='choice' else 0
            fixed.update(kind=(Literal[slot['kind']],...),image_id=(Literal[slot['image_id']],...),
                         options=(list[str],Field(min_length=count,max_length=count)))
        row = create_model(f'Cell_{index}_{price}',__base__=MixedClue if mixed else Clue,**fixed)
        fields[f'q{price}'] = (row,...)
    return create_model(f'Topic_{index}_Cells',__config__=ConfigDict(extra='forbid'),**fields)


class OllamaQuiz(OpenAIQuiz):
    def availability(self):
        try:
            model = local_model()
        except RuntimeError as error:
            return False,str(error)
        try:
            response = httpx.get(URL+'/api/tags', timeout=2, trust_env=False)
            response.raise_for_status()
            names = {m['name'] for m in response.json()['models']}
            if model not in names:
                return False, 'Модель ещё не загружена. Запустите Start-Local-AI.ps1.'
            return True, 'Локальная модель '+model+'. Без оплаты API; подготовка может занять несколько минут.'
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return False, 'Ollama не запущена. Запустите Start-Local-AI.ps1, затем обновите страницу.'

    @property
    def configured(self):
        return self.availability()[0]

    def request(self, instructions, data, schema, tokens):
        model = local_model()
        stage = 'grading' if schema is Verdict else 'review' if schema is EditorialReview else 'repair' if 'issues' in data else 'generation'
        request_id = start_request('ollama/'+model, stage,local=True)
        started, body, status = time.monotonic(), None, 'transport_error'
        try:
            response = httpx.post(URL+'/api/chat', json={
                'model': model, 'stream': False, 'keep_alive': '30m',
                'messages': [{'role':'system','content':instructions+'\nОтвечай только JSON на русском языке.'+('\nОбъяснение — одно короткое предложение.' if schema is Verdict else '')},
                             {'role':'user','content':json.dumps(data, ensure_ascii=False)}],
                'format': schema.model_json_schema(),
                'options': {'temperature':0.2, 'num_ctx':8192, 'num_predict':min(tokens,256 if schema is Verdict else 4500)}
            }, timeout=90 if schema is Verdict else 600, trust_env=False)
            status = 'http_error'
            response.raise_for_status()
            body = response.json()
            status = 'invalid_output'
            if not isinstance(body,dict) or body.get('done') is not True or body.get('done_reason') == 'length':
                raise ValueError('Incomplete output')
            result = schema.model_validate_json(body['message']['content']).model_dump()
            status = 'completed'
            return result
        except httpx.TimeoutException:
            status = 'timeout'
            raise RuntimeError('Локальная модель не успела ответить. Закройте тяжёлые приложения и попробуйте снова. Платные API не использовались.') from None
        except httpx.HTTPError:
            raise RuntimeError('Локальная модель недоступна. Проверьте Ollama и загрузку модели; OpenAI не используется.') from None
        except (ValueError, KeyError, TypeError):
            raise RuntimeError('Локальная модель вернула некорректный ответ. Попробуйте подготовить новую партию.') from None
        finally:
            finish_local_request(request_id,status,round((time.monotonic()-started)*1000),body)

    def generate(self, topics, on_progress=None):
        # Small batches fit the local context window and preserve accepted topics.
        with GENERATION_LOCK:
            return self._generate_topics(topics,on_progress)

    def _generate_topics(self, topics, on_progress=None):
        mixed = len(topics) == 8
        plan = format_plan(topics) if mixed else []
        rules = RULES.replace('Ровно 25 разных вопросов: topic_index 0..4, в каждой теме цены 100,200,300,400,500.',
            'Создай только пять вопросов для заданного topic_index: цены 100,200,300,400,500.')
        rules += '\nПиши компактно: question — до 160 символов; explanation — одно предложение до 140 символов; aliases — от 0 до 2 синонимов.'
        if mixed:
            rules += ('\nСоблюдай plan: kind и image_id неизменны. open и riddle: options=[]. '
                'riddle — однозначная загадка по теме. choice: ровно 4 разных коротких '
                'правдоподобных варианта, один дословно равен answer. image: вопрос требует '
                'осмотра назначенной картинки из images; options=[]. Для остальных image_id="".')
        accepted = []
        for index, topic in enumerate(topics):
            if on_progress:
                on_progress(f'Тема {index+1} из {len(topics)}: «{topic}». Готово вопросов: {len(accepted)}.')
            context = {'topic':topic,'topic_index':index}
            slots = []
            if mixed:
                slots = [p for p in plan if p['topic_index']==index]
                context.update(plan=slots, images={p['image_id']:IMAGE_CATALOG[p['image_id']] for p in slots if p['image_id']})
            clues, issues = [], []
            prices = list(range(100,501,100))
            for attempt in range(3):
                if attempt and on_progress:
                    on_progress(f'Исправляем тему {index+1} из {len(topics)}: «{topic}». Попытка {attempt+1} из 3.')
                payload = context if attempt == 0 else {**context,'clues':clues,'issues':issues}
                instruction = '\nВерни объект q100,q200,q300,q400,q500 по схеме.' if attempt == 0 else '\nЗамени ТОЛЬКО вопросы с замечаниями, перечисленные в схеме. Остальные сервер сохранит.'
                schema = cells_schema(index,slots,prices,mixed)
                replacements = self.request(rules+instruction,payload,schema,4500)
                by_price = {q['price']:q for q in clues}
                by_price.update({p:replacements[f'q{p}'] for p in prices})
                clues = [by_price[p] for p in range(100,501,100)]
                issues = obvious_issues(topics,clues)
                seen = set()
                for clue in clues:
                    normalized = normalize(clue['question'])
                    if normalized in seen:
                        issues.append(dict(topic_index=index,price=clue['price'],reason='Вопрос повторяет предыдущий.'))
                    seen.add(normalized)
                    if not mixed:
                        continue
                    try:
                        validate_mixed([clue],[s for s in slots if s['price']==clue['price']],expected_count=1)
                    except (ValueError,KeyError) as error:
                        issues.append(dict(topic_index=index,price=clue['price'],reason=str(error)))
                if not issues:
                    if on_progress:
                        on_progress(f'Редактор проверяет тему {index+1} из {len(topics)}: «{topic}».')
                    issues = self.request(rules+'\nТы независимый редактор. Проверь эти пять вопросов: '
                        'факты, эталоны, тематичность, справедливую сложность. Возвращай issues только '
                        'при существенной ошибке, утечке ответа или банальности. Не придирайся к стилю. '
                        'Каждая причина — до 80 символов. Если всё хорошо, issues=[].', {**context,'clues':clues},EditorialReview,1200)['issues']
                if not issues:
                    accepted.extend(clues)
                    break
                prices = sorted({issue.get('price') for issue in issues if issue.get('topic_index')==index and issue.get('price') in by_price}) or list(by_price)
            else:
                raise RuntimeError('Локальный редактор не смог подготовить тему «'+topic+'» после трёх попыток. Уточните тему и попробуйте снова.')
        result = validate_pack({'clues':accepted},len(topics))
        if mixed:
            validate_mixed(result,plan)
        return result


def quiz_provider():
    provider = settings()['AI_PROVIDER'].strip().lower()
    if provider == 'ollama':
        return OllamaQuiz()
    if provider == 'openai':
        return OpenAIQuiz()
    raise RuntimeError('AI_PROVIDER должен быть ollama или openai. Автоматического переключения нет.')
