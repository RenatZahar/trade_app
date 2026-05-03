# Iteration 09 - Agentic-ready contours

## Тема

Agentic-ready контуры runtime-сценариев.

## Junior+ компетенция

Junior+ умеет проектировать runtime-действия так, чтобы ими мог безопасно
управлять внешний orchestration-слой: CLI, CI, dashboard или агент.

## Статус

Done

## Контекст старта

- `iteration_08` закрыла минимальный GitHub Actions quality gate.
- Проект уже имеет единый runtime logging слой:
  - `logs/<run_id>.log` для человекочитаемых логов;
  - `RunTracker` для состояния run/stage lifecycle;
  - `_TRACKER_INFO` события в общем лог-потоке.
- В проекте уже есть частичные idempotency/resume-подходы в data maintenance
  задачах, но для обычных runtime-сценариев контракт еще не оформлен явно.
- Для задач с SQLite, bulk data, индексами и maintenance-сценариями продолжает
  действовать hard stop: сначала design review альтернатив, затем реализация
  выбранного варианта.

## Цель итерации

Сделать первый безопасный срез agentic-ready outputs:

- не менять существующий формат `logs/<run_id>.log`;
- не парсить текстовые логи обратно в структуру;
- писать machine-readable artifacts напрямую из `RunTracker`;
- зафиксировать минимальный формат `manifest.json`, `events.jsonl`,
  `summary.json`;
- покрыть новый контракт быстрыми smoke/unit тестами.

## Границы

В scope:

- `modules/logger/*`;
- быстрые `tests/unit_smoke`;
- документация итерации.

Не в scope:

- SQLite bulk operations;
- изменение модели `run_id`;
- перенос существующих логов из `logs/<run_id>.log` в новую структуру;
- полноценный resume всех сценариев;
- парсинг старых log-файлов;
- dashboard/UI.

## Риски

- Нельзя превращать agent artifacts во второй независимый источник истины.
- Нельзя ломать существующие runtime logs, потому что они уже используются для
  диагностики.
- `events.jsonl` должен дописываться по ходу сценария, чтобы при падении
  оставалась последняя структурная точка.
- `summary.json` должен появляться при любом корректном `run_finished`, включая
  сценарии, которые завершают tracker вручную.

## Варианты

### Minimal patch

- Добавить writer рядом с logging/tracker слоем.
- Писать agent artifacts из текущего `RunTracker`.
- Оставить текущие текстовые логи без изменений.

Плюсы: низкий риск, быстрый проверяемый контракт.

Минусы: пока без полноценного idempotency/resume контракта для каждого сценария.

### Medium refactor

- Перевести все tracker-события на единый structured event object.
- Текстовый `_TRACKER_INFO` строить из того же объекта.

Плюсы: чище архитектурно.

Минусы: больше blast radius в logging/runtime коде.

### Long-term option

- Ввести отдельный runtime result API для всех сценариев:
  `ScenarioResult`, `ScenarioEvent`, `ArtifactManifest`.

Плюсы: сильный контракт для агентов, CI и будущего UI.

Минусы: требует отдельного проектирования и миграции сценариев.

## Выбранный план

Начать с `Minimal patch`:

1. Добавить `modules/logger/agent_outputs.py`.
2. На старте run писать `manifest.json`.
3. На lifecycle-событиях писать `events.jsonl`.
4. На `run_finished` писать `summary.json`.
5. Покрыть writer и runtime bootstrap smoke-тестами.
6. Не менять существующий `logs/<run_id>.log`.

## Текущий результат

- Добавлен writer:
  `modules/logger/agent_outputs.py`.
- Agent artifacts пишутся в:
  `logs/agent_runs/<run_id>/`.
- Формат:
  - `manifest.json` - входы, metadata, run id, ссылки на artifacts;
  - `events.jsonl` - поток lifecycle-событий;
  - `summary.json` - финальное состояние run из `RunTracker.get_run_data()`.
- Existing text logs остаются в:
  `logs/<run_id>.log`.
- `summary.json` пишется через общий `log_tracker_run_event(...,
  "run_finished")`, чтобы покрыть сценарии с ручным завершением tracker.

## Проверки

- `python -m pytest tests\unit_smoke\test_agent_outputs.py -q` ->
  `2 passed`.
- `python -m pytest tests\unit_smoke\test_runtime_bootstrap.py tests\unit_smoke\test_run_tracker.py -q` ->
  `12 passed`.
- `python -m pytest tests\unit_smoke -q` ->
  `58 passed, 1 warning`.

## Follow-up

- Idempotency/resume contract по сценариям:
  - `start_parser`:
    - resume по старому `run_id` не нужен;
    - каждый запуск получает новый `run_id`;
    - safe rerun уже обеспечивается через состояние данных: parser смотрит
      последний скачанный блок в SQLite и строит новый список блоков;
    - продолжение "с середины stage" нерационально, потому что один цикл
      небольшой, а потери при повторе минимальны;
    - source of truth для продолжения - SQLite/blockchain state, а не tracker.
  - `main-pipeline`:
    - полноценный stop/resume contract потенциально самый полезный именно здесь;
    - сейчас реализацию откладываем, чтобы не цементировать текущий способ
      сбора данных;
    - возвращаться к этому нужно после переделки data collection/artifact layer.
  - `param-grid`:
    - сценарий ниже по приоритету, чем `main-pipeline`;
    - stop/resume и политика повторного запуска требуют отдельной проработки
      позже;
    - текущие parquet artifacts могут стать частью будущего контракта, но
      решение пока не принимается.
- Главный вывод: agentic-ready не означает одинаковый resume-механизм для всех
  сценариев. Для parser достаточно safe rerun через состояние БД, а полноценный
  resume по run artifacts имеет смысл проектировать после стабилизации
  `main-pipeline` data-flow.

## Итог

- Первый agentic-ready контур внедрен в logging/runtime слой без изменения
  существующего `logs/<run_id>.log`.
- Runtime lifecycle теперь оставляет машинно-читаемые artifacts:
  - `logs/agent_runs/<run_id>/manifest.json`;
  - `logs/agent_runs/<run_id>/events.jsonl`;
  - `logs/agent_runs/<run_id>/summary.json`.
- Agent artifacts строятся напрямую из `RunTracker`, без парсинга текстовых
  логов.
- Формат artifacts признан достаточным для текущего этапа.
- Stop/resume решение зафиксировано как архитектурный вывод:
  - для `start_parser` отдельный resume по `run_id` не нужен;
  - для `main-pipeline` полноценный stop/resume отложен до переделки data
    collection/artifact layer;
  - `param-grid` оставлен как низкоприоритетная последующая проработка.

## DoD

- [x] Machine-readable artifacts создаются без парсинга текстовых логов.
- [x] `manifest.json` создается на старте run.
- [x] `events.jsonl` дописывается по lifecycle-событиям.
- [x] `summary.json` создается на `run_finished`.
- [x] Существующий `logs/<run_id>.log` не меняет расположение и формат.
- [x] Добавлены быстрые smoke/unit тесты.
- [x] Прогнать полный `tests/unit_smoke`.
- [x] Зафиксировать follow-up по idempotency contract для выбранных сценариев.
