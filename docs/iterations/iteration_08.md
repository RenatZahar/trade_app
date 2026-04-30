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

## Definition of Done

- [ ] Добавлен GitHub Actions workflow для минимального quality gate.
- [ ] Workflow запускает `python -m pytest tests\unit_smoke -q`.
- [ ] CI не требует live services и не мутирует данные.
- [ ] Локальная команда quality gate проходит.
- [ ] Документ итерации обновлен итогом, проверками и known warnings.

