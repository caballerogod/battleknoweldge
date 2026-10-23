# Сторонние компоненты

Концепты `docs/game-hub-concept.png` и `docs/trivia-board-concept.png` созданы встроенным ImageGen для выбора двух игр и поля «Своей игры». Они используют уже существующее художественное направление студии. В рабочем интерфейсе остаются настоящие HTML-кнопки, поля и состояние, отдельные новые тяжёлые графические зависимости не используются.

Серверный адаптер OpenAI Responses API использует уже имеющийся httpx. Для запросов необходим пользовательский API-ключ; библиотека и проект не предоставляют доступ к платной модели. Демовопросы получены из локального авторского банка приложения и не выдаются за ответ OpenAI.

`frontend/public/images/show-stage.webp` — отдельный фон студии, созданный встроенным ImageGen для нового игрового экрана. Концепты сохранены в `docs/show-stage-concept.png` и `docs/show-result-concept.png`; они не заменяют HTML-интерфейс. Весь текст, состояния, таймер и управление реализованы кодом. Сведения о брифе — `docs/SHOW_DESIGN_RU.md`.

Локальный шрифт Cormorant Garamond получен из Google Fonts, автор Christian Thalmann. Лицензия SIL Open Font License 1.1 сохранена в `frontend/public/fonts/OFL-Cormorant-Garamond.txt`. Шрифт не требует обращения к внешнему сервису при запуске игры.

Приложение использует npm-пакеты React, React DOM, Vite, TypeScript, Vitest, lucide-react и @mediapipe/tasks-vision; Python-пакеты FastAPI, Uvicorn, SQLAlchemy, Pydantic, pytest и httpx. Их версии фиксируются package-lock.json и backend/requirements-lock.txt. Условия лицензирования библиотек смотрите в установленных пакетах и их официальных репозиториях.

MediaPipe Tasks Vision: версия 0.10.32. WASM-файлы в frontend/public/wasm скопированы из этого npm-пакета скриптом frontend/scripts/setup-mediapipe.mjs.

Модель Gesture Recognizer (float16, version 1):
https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task

Размер проверенного файла: 8 373 440 байт.
SHA-256: `97952348cf6a6a4915c2ea1496b4b37ebabc50cbbf80571435643c455f2b0482`.

Руководство, возможности и сведения о модели:
https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer

Необязательный веб-шрифт Manrope загружается из Google Fonts с системным резервным шрифтом Segoe UI.

docs/design-concept.png — визуальный ориентир, созданный встроенным ImageGen для этого проекта. Изображение не используется вместо работающего интерфейса и не является скриншотом приложения. Иллюстрация меню построена средствами CSS, а интерфейс — React и CSS. Параметры генерации: полный русский экран викторины, тёмная палитра, фиолетовый основной акцент, золотой XP, боковая навигация, вопрос с четырьмя вариантами и панель камеры/голоса. Исходный запрос генерации сохранён в docs/DESIGN_PROMPT.txt.

Звуки `frontend/public/audio/*.wav` — короткие фрагменты записи «Кто хочет стать миллионером?» от 18 ноября 2007 года, из указанного пользователем источника: https://www.youtube.com/watch?v=Yzhau6No0KY . Это материалы передачи, а не оригинальная музыка проекта; права принадлежат соответствующим правообладателям. Отдельная лицензия от правообладателей не установлена и не включена в проект. Источник, назначения и таймкоды приведены в `frontend/public/audio/sources.json`. Скрипт `frontend/scripts/extract-reference-audio.py` выполняет только нарезку, фильтрацию и изменение громкости; полная запись выпуска в поставку не включена. WAV доступны локально и не требуют сетевого музыкального/TTS API. Старый генератор синтетических звуков пишет в отдельную резервную папку и не используется игрой.

### Rubik
Локальный вариативный Rubik с кириллицей: frontend/public/fonts/rubik-variable.ttf.
Источник: https://github.com/google/fonts/tree/main/ofl/rubik .
Лицензия SIL Open Font License 1.1: frontend/public/fonts/Rubik-OFL.txt.
Используется только в «Своей игре». Точный телевизионный шрифт не идентифицировался; воспроизведены плотность и характер референса.

### Локальные иллюстрации вопросов
frontend/public/quiz-images/*.svg — собственные векторные рисунки и схемы, созданные кодом для проекта. cat.svg — оригинальная визуальная загадка-отсылка с котом, не копия оригинального комикса или кадр мема. Для формата image используются только идентификаторы из серверного каталога; внешние изображения не скачиваются.


## Локальный AI runtime (в архив не включён)

Ollama: [официальный проект и лицензия](https://github.com/ollama/ollama), MIT. Qwen3 4B Instruct: [карточка и лицензия модели](https://ollama.com/library/qwen3:4b-instruct), Apache 2.0 по карточке. CPU-библиотеки извлечены из официального Windows-архива Ollama 0.40.9; сопутствующие LICENSE-файлы сохранены в каталоге runtime. Веса загружаются из официального registry Ollama и проверяются SHA256. Интеграция не требует нового Python/JS SDK, использует уже установленный httpx.
