# Iteration 10 - Portfolio packaging

## Тема

Портфолио-упаковка проекта.

## Junior+ компетенция

Junior+ умеет показывать проект как инженерный продукт: объяснять назначение,
архитектуру, запуск, ограничения, проверки и дальнейший roadmap так, чтобы
читатель мог быстро оценить зрелость проекта без чтения всего кода.

## Статус

Done

## Контекст старта

- `iteration_09` закрыта, слита в `main_branch` и запушена.
- Рабочая ветка десятой итерации:
  `feature/iteration-10-portfolio-packaging`.
- На старте в корне репозитория нет `README.md`.
- В проекте уже есть важные инженерные контуры, которые нужно показать в
  портфолио-формате:
  - CLI/runtime entrypoint через `main.py` и `cli_args.py`;
  - runtime scenario слой в `runtime_scenarios.py`;
  - centralized settings/runtime contracts;
  - runtime logging и machine-readable agent artifacts;
  - быстрый smoke/unit gate: `python -m pytest tests\unit_smoke -q`;
  - GitHub Actions quality gate.
- Для больших данных, SQLite, bulk operations, индексов и maintenance задач
  продолжает действовать hard stop: сначала design review альтернатив, затем
  только выбранная реализация.

## Цель итерации

Сделать первичную README-упаковку проекта как инженерного продукта:

- кратко объяснить назначение проекта;
- описать архитектуру и основные runtime-сценарии;
- дать quickstart без секретов и без требования live data;
- показать, какие проверки есть локально и в CI;
- зафиксировать known limits честно, без скрытия private/live зависимостей;
- добавить roadmap/follow-up на ближайшие улучшения.

## Границы

В scope:

- `README.md`;
- при необходимости маленькие docs-only уточнения в `docs/`;
- примеры команд запуска;
- описание sample logs / agent artifacts на уровне формата и путей.

Не в scope:

- изменение runtime behavior;
- изменение `.env` или секретов;
- запуск live SQLite/Redis/Bitcoin Core/Flask сценариев;
- bulk DB операции, migrations, индексы, `VACUUM`, `ANALYZE`;
- перенос private strategy logic в public README;
- полноценная ревизия всех заметок `docs/` - это тема `iteration_11`.

## Риски

- README может случайно раскрыть private/project-specific детали, которые не
  должны быть публичной витриной.
- Quickstart не должен обещать запуск live-сценариев без локальных сервисов и
  данных.
- Нельзя смешивать portfolio packaging с рефакторингом runtime-кода.
- Нужно честно отделить reproducible smoke/demo контур от live data pipeline.
- Документация должна отражать фактические команды и файлы, а не желаемую
  архитектуру.

## Варианты

### Minimal patch

- Создать `README.md` с разделами:
  overview, architecture, quickstart, runtime scenarios, logs/artifacts,
  tests/CI, known limits, roadmap.
- Не менять код.

Плюсы: низкий риск, быстро закрывает главную дыру портфолио.

Минусы: без глубокого docs cleanup, часть деталей останется в `docs/`.

### Medium docs pass

- Создать `README.md`.
- Дополнительно привести 1-2 docs-файла к ссылочной структуре из README.

Плюсы: README лучше связан с внутренней документацией.

Минусы: выше риск расползания scope в итерацию 11.

### Productized demo option

- README + отдельный demo mode / sample data / пример логов как committed
  artifact.

Плюсы: сильнее для портфолио и внешнего ревью.

Минусы: требует проектирования public/private boundary и может затронуть
runtime/data flow; лучше оставить как следующий шаг после README baseline.

## Выбранный план

Начать с `Minimal patch`:

1. Сверить реальные команды и entrypoints:
   - `main.py`;
   - `cli_args.py`;
   - `runtime_scenarios.py`;
   - `tests/unit_smoke`;
   - `.github/workflows/quality-gate.yml`.
2. Создать `README.md` как честную витрину текущего состояния.
3. Указать quickstart вокруг setup и smoke tests, без live-сервисов по
   умолчанию.
4. Описать live scenarios отдельно как requiring local services/data.
5. Зафиксировать known limits и roadmap.
6. Прогнать `python -m pytest tests\unit_smoke -q`, потому что docs-only
   изменение не должно ломать baseline.

## Решения по процессу

- При закрытии каждой будущей итерации добавлен обязательный
  `README impact check`.
- Если итерация меняет публично объясняемые факты проекта - CLI, runtime
  scenarios, env/config, logs/artifacts, tests/CI, architecture, known limits
  или roadmap - `README.md` обновляется до финального commit/merge.
- Если влияния на README нет, в итогах итерации нужно фиксировать
  `README impact: none`.
- Если влияние есть, но README сознательно откладывается, это фиксируется как
  явный follow-up и требует принятого пользователем отложения.

## Текущий результат

- Добавлен основной англоязычный `README.md`.
- Добавлена русская версия `README.ru.md` с взаимной ссылкой из основного
  README.
- README оформлен как короткая public portfolio витрина, а не как полный
  внутренний engineering manual.
- Trading, Bitcoin и ML упомянуты честно: проект описан как учебный
  engineering project, а не как production trading software.
- Live-зависимости перечислены явно:
  - SQLite data;
  - Redis;
  - Bitcoin Core / Bitcoin RPC;
  - Flask runtime;
  - локальные price/model/data artifacts.
- Quickstart ограничен безопасным baseline:
  - установка зависимостей из `requirements.lock.txt`;
  - `python -m pytest tests\unit_smoke -q`;
  - `python main.py --help`.
- Runtime-сценарии отделены от безопасного smoke quickstart и помечены как
  требующие локальных сервисов/данных.

## README impact

Applied: текущая итерация создала README baseline, поэтому публичные факты
проекта теперь зафиксированы в `README.md` и `README.ru.md`.

## Проверки

- `python main.py --help` -> pass.
- `python -m pytest tests\unit_smoke -q` -> `58 passed, 1 warning`.
- Known warning: pandas `DataFrameGroupBy.apply` deprecation warning в
  `modules/teach_and_update_models/data_operations.py`.

## Industry note (de-facto alternatives)

- Выбранный подход в итерации: README-first portfolio packaging.
- Альтернатива (de-facto): отдельный docs site (`mkdocs`, `sphinx`,
  GitHub Pages) с architecture decision records.
- Почему не берем сейчас: в проекте еще нет даже корневого README; docs site
  будет преждевременной инфраструктурой до базовой упаковки.
- Мини-пример:
  ```bash
  python -m pytest tests\unit_smoke -q
  python main.py --help
  ```

## Definition of Done

- [x] В корне репозитория есть `README.md`.
- [x] README описывает project overview и architecture.
- [x] README содержит quickstart без секретов и live service requirements.
- [x] README показывает основные runtime commands или способ их посмотреть.
- [x] README описывает logs и machine-readable agent artifacts.
- [x] README фиксирует tests/CI command.
- [x] README честно перечисляет known limits.
- [x] Прогнан `python -m pytest tests\unit_smoke -q`.
- [x] Итог итерации обновлен в этом документе.
