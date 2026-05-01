# Iteration 08 - Minimal quality gate in CI

## Тема

Минимальный quality gate в CI.

## Junior+ компетенция

Junior+ умеет предотвращать очевидные регрессии до merge: запускать быстрые
проверки автоматически, понимать стоимость CI и отделять обязательный gate от
дополнительных quality checks.

## Статус

Started

## Контекст старта

- `iteration_07` закрыта и слита в `main_branch`.
- Рабочая ветка восьмой итерации:
  `feature/iteration-08-quality-gate-ci`.
- В репозитории на старте нет `.github/workflows`, поэтому CI нужно вводить
  с минимального, проверяемого baseline.
- Уже есть быстрый локальный сигнал:
  `python -m pytest tests\unit_smoke -q`.
- Последний локальный прогон перед стартом:
  `44 passed, 1 warning`.
- Предупреждение известно и не блокирует итерацию:
  pandas `DataFrameGroupBy.apply` в
  `modules/teach_and_update_models/data_operations.py`.

## Цель итерации

Добавить минимальный GitHub Actions quality gate, который:

- запускается на pull request / push в основные ветки;
- устанавливает зависимости воспроизводимо;
- запускает быстрые smoke/unit checks;
- падает при регрессии P0/P1-проверок;
- не требует live SQLite DB, Redis, Bitcoin Core, Flask server или внешних
  сервисов.

## Границы

В scope:

- `.github/workflows/...`;
- минимальная настройка pytest/CI env, если нужна;
- документация запуска quality gate;
- маленькие правки тестов только если они делают smoke suite CI-safe без
  изменения runtime behavior.

Не в scope:

- полноценный deployment;
- live integration tests;
- долгие DB/data maintenance проверки;
- lint на весь проект, если он создаст большой unrelated backlog;
- рефакторинг ML/data pipeline ради прохождения CI.

## Риски

- `requirements.lock.txt` может содержать тяжелые или platform-sensitive
  зависимости.
- Smoke tests должны оставаться без live DB mutation и без внешних сервисов.
- Нельзя включать integration-live тесты в обязательный gate без отдельного
  окружения.
- Если сразу включить строгий lint, итерация может превратиться в большой
  formatting/refactor task вместо quality gate.

## Предварительный план

1. Проверить текущие dependency files и pytest config.
2. Добавить минимальный workflow:
   - checkout;
   - setup Python;
   - install dependencies from `requirements.lock.txt`;
   - run `python -m pytest tests\unit_smoke -q`.
3. При необходимости добавить cache для pip, но не усложнять первый вариант.
4. Локально проверить команду, которую будет запускать CI.
5. Зафиксировать в документе:
   - какие проверки стали gate;
   - какие проверки отложены;
   - known warning.

## Варианты

### Minimal patch

- Один GitHub Actions workflow только для `tests/unit_smoke`.
- Без lint на первом шаге.

Плюсы: быстрый и низкорисковый gate.

Минусы: не ловит style/type issues.

### Medium refactor

- Workflow + базовый lint по ограниченному набору файлов.

Плюсы: больше инженерного сигнала.

Минусы: может потребовать отдельный cleanup, если lint еще не введен в проект.

### Strict gate

- Tests + lint + type checks + coverage.

Плюсы: сильный gate.

Минусы: слишком большой скачок для текущего состояния проекта.

## Рекомендация

Начать с `Minimal patch`: сделать обязательным то, что уже стабильно проходит
локально, а lint/type/coverage оформить как следующие улучшения после первого
зеленого CI.

## Отложенные проверки и правила

- Lint всего проекта не входит в обязательный gate восьмой итерации. Хвост:
  вернуться к постепенному lint baseline в `iteration_11`, когда фокус будет на
  ревизии и гигиене проекта.
- Проверки live DB, Redis, Bitcoin RPC, Flask server и внешних сервисов не
  входят в GitHub Actions gate. Для runtime-сценариев правило такое: внешние
  сервисы поднимаются или проверяются в начале сценария; при ошибке сценарий
  должен прерываться с понятным логом/записью в tracker.
- Проверка обязательных env-переменных допустима в smoke suite только как
  контракт конфигурации: тест не должен требовать реальные секреты или доступ к
  live-сервисам.

## Уточненный план после обсуждения

1. Оставить GitHub Actions quality gate на конец итерации: сначала внести и
   проверить локальные изменения, затем добавить workflow и проверить его на
   GitHub.
2. Сверить dependency lock:
   - найти или восстановить способ генерации `requirements.lock.txt`;
   - если проектного скрипта нет, зафиксировать явную команду обновления lock;
   - не смешивать lock с лишними пакетами из случайного глобального окружения.
   - текущий lock генерируется из активного Python 3.12 окружения; конфликтующий
     `dask-expr==1.0.14` исключен из freeze, потому что он требует другой
     `dask`, а проект напрямую использует `dask`/`distributed`.
3. Добавить smoke-проверки config contract:
   - validator знает обязательные env-переменные;
   - отсутствие обязательной переменной дает понятную ошибку;
   - тесты не требуют реальных секретов, live DB или внешних сервисов.
4. Ввести или зафиксировать runtime preflight для сценариев:
   - каждый сценарий декларирует нужные зависимости перед долгой работой в
     едином runtime contract;
   - Redis, Bitcoin RPC, Flask и другие live-сервисы проверяются/поднимаются в
     начале соответствующего сценария;
   - при ошибке сценарий прерывается с понятным логом и/или tracker event.
5. Покрыть сценарии smoke-тестами на уровне контрактов:
   - тестировать не реальный Redis/Bitcoin/Flask, а то, что сценарий вызывает
     нужный preflight до основной работы;
   - использовать monkeypatch/fakes для проверки порядка вызовов и ошибок.
6. В конце итерации добавить минимальный `.github/workflows/...`:
   - checkout;
   - setup Python;
   - install from `requirements.lock.txt`;
   - run `python -m pytest tests/unit_smoke -q`.
7. Закрыть итерацию:
   - локально прогнать `python -m pytest tests\unit_smoke -q`;
   - проверить GitHub Actions run;
   - обновить итог, known warnings и отложенные хвосты.

## Industry note (de-facto alternatives)

- Выбранный подход в итерации: минимальный обязательный GitHub Actions gate
  для `tests/unit_smoke`.
- Альтернатива (de-facto): разделить CI на обязательный быстрый gate и
  необязательные extended checks (`lint`, `type checks`, coverage, integration).
- Почему не берем сейчас: в проекте еще нет baseline workflow, поэтому сначала
  нужен стабильный зеленый gate без live services и длинных data checks.
- Мини-пример:
  ```yaml
  - name: Run smoke/unit tests
    run: python -m pytest tests/unit_smoke -q
  ```

## Definition of Done

- [x] Добавлен GitHub Actions workflow для минимального quality gate.
- [x] Workflow запускает `python -m pytest tests\unit_smoke -q`.
- [x] CI не требует live services и не мутирует данные.
- [x] Локальная команда quality gate проходит.
- [ ] Документ итерации обновлен итогом, проверками и known warnings.
