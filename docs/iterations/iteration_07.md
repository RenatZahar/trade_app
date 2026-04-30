# Iteration 07 - Module responsibility boundaries

## Тема

Границы ответственности модулей.

## Junior+ компетенция

Junior+ умеет отделять orchestration от бизнес-логики и I/O, удерживать
модули в понятных границах и объяснять, где должен находиться конкретный
тип поведения.

## Статус

Started

## Контекст старта

- `iteration_06` закрыла детерминизм, experiment metadata, runtime bootstrap,
  CLI cleanup и быстрый `unit_smoke` сигнал.
- `iteration_06` слита в `main_branch` и запушена на origin.
- Рабочая ветка седьмой итерации:
  `feature/iteration-07-module-responsibility-boundaries`.
- На старте ветка создана от актуальной `main_branch`.
- В проекте уже видны кандидаты на разбор границ:
  - `main.py`;
  - `main_functions.py`;
  - `modules/teach_and_update_models/orchestrator.py`;
  - `modules/logger/runtime_bootstrap.py`;
  - CLI слой в `cli_args.py`;
  - runtime/logging/experiment metadata слой.

## Цель итерации

Сделать границы между entrypoint, orchestration, бизнес-логикой и I/O
понятнее без большого rewrite.

Практический фокус:

- уточнить, что должно оставаться в `main.py`;
- отделить CLI parsing от runtime orchestration;
- отделить orchestration от вычислительных/pure-ish функций там, где это
  безопасно;
- уменьшить риск циклических импортов и скрытых side effects;
- улучшить тестируемость P0/P1-границ без Redis, Bitcoin Core и большой БД.

## Затронутые темы

- orchestration vs business logic;
- entrypoint boundaries;
- I/O boundaries;
- side effects;
- import boundaries;
- testable seams;
- agent workflow infrastructure as unexpected iteration support work.

## Непредусмотренный пункт на старте итерации

Перед практической работой по модульным границам была выполнена отдельная
инфраструктурная работа по правилам взаимодействия с Codex:

- создан корневой `AGENTS.md`;
- созданы repo-scoped skills в `.agents/skills/`;
- оформлены workflow:
  - `data-pipeline-safety-check`;
  - `discuss-plan-execute`;
  - `review-python-module`;
  - `iteration-workflow`;
  - `experiment-protocol`;
- русское пояснение вынесено в `docs/agents_skills_translate_ru.md`;
- decision records для экспериментов вынесены в `docs/experiments/`;
- старые черновики `docs/AGENTS_demo.md` и `docs/agents_skills_demo.md`
  удалены после переноса полезного содержания.

Этот пункт не был исходной темой `iteration_07`, но он влияет на то, как
дальше вести итерацию: теперь для risky DB задач, экспериментов, ревью и
закрытия итераций есть отдельные agent workflows.

## Короткая теория перед практикой

Граница ответственности модуля отвечает на вопрос: "какое решение этот слой
имеет право принимать?"

Рабочее разделение для проекта:

- entrypoint (`main.py`) принимает запуск и делегирует дальше;
- CLI слой разбирает аргументы и не запускает тяжелые side effects сам;
- orchestration слой решает порядок шагов;
- бизнес-логика считает результат по входным данным;
- I/O слой читает и пишет внешние системы: SQLite, файлы, Redis, Bitcoin Core,
  logs;
- tests должны по возможности цепляться за стабильные границы, а не за
  случайные внутренние детали.

## Предварительный диагноз

- P0/P1: после `iteration_06` `main.py` стал тоньше, но нужно проверить, не
  остались ли orchestration обязанности в неподходящих слоях.
- P1: `main_functions.py` исторически смешивал orchestration, infrastructure
  calls и side effects; это главный кандидат на разбор.
- P1: ML orchestration и data operations требуют аккуратного разделения:
  нельзя одновременно менять поведение pipeline и переносить код ради красоты.
- P1: новые agent workflows помогают процессу, но их нужно считать
  инфраструктурным контекстом, а не заменой инженерного анализа кода.

## Кандидаты на первый срез

- `main.py` - проверить, что entrypoint остается тонким.
- `cli_args.py` - проверить, где заканчивается parsing и начинается runtime.
- `main_functions.py` - найти смешанные обязанности и side effects.
- `modules/teach_and_update_models/orchestrator.py` - оценить, где
  orchestration смешивается с model/data details.
- `modules/logger/runtime_bootstrap.py` - проверить границу runtime startup /
  shutdown.

## Варианты вмешательства

### Minimal patch

- Сделать обзор текущих границ.
- Выбрать 1-2 самые безопасные точки для локального улучшения.
- Добавить или уточнить smoke/unit тесты только для стабильных контрактов.

Плюсы: низкий риск, хорошо подходит после большого среза `iteration_06`.

Минусы: не решит всю архитектуру сразу.

### Medium refactor

- Выделить несколько helper/orchestration функций из `main_functions.py`.
- Уточнить слой CLI/runtime/orchestration.
- Добавить тесты на новые границы.

Плюсы: заметнее улучшит структуру.

Минусы: выше риск случайно поменять runtime behavior.

### Rewrite slice

- Пересобрать один крупный pipeline вокруг явных объектов/контрактов.

Плюсы: потенциально чище долгосрочно.

Минусы: слишком рискованно для старта итерации; сначала нужен обзор и
минимальный срез.

## Рекомендация на старт

Начать с `Minimal patch`.

Причина: тема итерации про границы ответственности, но после `iteration_06`
уже было много изменений в entrypoint/runtime/metadata. Сначала нужно
зафиксировать текущую карту границ и выбрать маленький безопасный срез.

## Definition of Done

- [ ] Текущие границы `main.py` / `cli_args.py` / `main_functions.py` /
  runtime/logging/orchestration описаны в документе итерации.
- [ ] Выбран минимальный практический срез без крупного rewrite.
- [ ] Внесены только scoped изменения, если они действительно нужны после
  обзора.
- [ ] Для измененного поведения есть быстрый тест или явно зафиксировано,
  почему тест не нужен.
- [ ] `python -m pytest tests\unit_smoke -q` проходит перед закрытием
  итерации, если были изменения в коде.
- [ ] Итог, ограничения и хвосты зафиксированы в этом документе.

## Командная памятка

Быстрые smoke/regression тесты:

```powershell
python -m pytest tests\unit_smoke -q
```

Проверка текущей ветки:

```powershell
git branch --show-current
git status -sb
```
