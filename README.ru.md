# trade_app

[English version](README.md)

`trade_app` - учебный инженерный проект вокруг Bitcoin-данных, trading research,
ML-пайплайна и надежного runtime-оркестрирования.

Главная ценность репозитория - не готовый торговый продукт. Это развивающийся
пример того, как data/ML-проект постепенно делать более воспроизводимым,
наблюдаемым, тестируемым и понятным для ревью.

## Инженерный фокус

Проект развивается через задокументированные Junior+ итерации. Текущий фокус:

- воспроизводимые runtime entrypoints;
- явная конфигурация и контракты runtime-зависимостей;
- структурное логирование и tracking запусков;
- machine-readable artifacts для agent/orchestration слоя;
- smoke/unit tests и минимальный GitHub Actions quality gate;
- понятная архитектура и честно описанные operational limits.

Заметки по итерациям лежат в [`docs/iterations`](docs/iterations).

## Архитектура

Верхнеуровневый поток:

```text
main.py
  -> cli_args.py
  -> runtime_scenarios.py
  -> modules/*
  -> logs/ и data artifacts
```

Ключевые области:

- `main.py` - единая локальная точка входа.
- `cli_args.py` - парсинг и валидация CLI-сценариев.
- `runtime_scenarios.py` - orchestration layer для runtime-сценариев.
- `settings/` - пути, runtime config и dependency contracts.
- `modules/logger/` - текстовые логи, run tracker и agent-readable outputs.
- `tests/unit_smoke/` - быстрые contract/smoke проверки.
- `.github/workflows/quality-gate.yml` - минимальный CI quality gate.

## Быстрый старт

Безопасная baseline-проверка не требует Bitcoin Core, Redis, Flask или live
мутаций базы данных.

```powershell
python -m pip install -r requirements.lock.txt
python -m pytest tests\unit_smoke -q
```

Посмотреть доступные runtime-команды:

```powershell
python main.py --help
```

## Runtime-сценарии

Текущий CLI содержит:

```powershell
python main.py main-pipeline
python main.py param-grid --test-fraction 0.1 --seed 42
python main.py --start_parser
python main.py test downloaded-from-btc-data 10 42
```

Это live/runtime-сценарии. Они могут требовать локальные сервисы, настроенные
пути и проектные данные. Для свежего checkout безопаснее сначала запускать
smoke-проверку из раздела выше.

## Runtime-зависимости

Контракты runtime-зависимостей описаны в
[`settings/runtime_contracts.py`](settings/runtime_contracts.py).

В зависимости от сценария проект может требовать:

- SQLite data по пути `BLOCKS_SQL_DATA`;
- Redis;
- Bitcoin Core / Bitcoin RPC;
- Flask runtime;
- локальные price/model/data artifacts.

Пример переменных окружения есть в [`.env.example`](.env.example).
Реальные секреты и локальные credentials нельзя коммитить.

## Логи и agent artifacts

Runtime logging пишет человекочитаемые логи в:

```text
logs/<run_id>.log
```

Agent-readable artifacts пишутся в:

```text
logs/agent_runs/<run_id>/manifest.json
logs/agent_runs/<run_id>/events.jsonl
logs/agent_runs/<run_id>/summary.json
```

Эти artifacts создаются напрямую из runtime tracker, без обратного парсинга
текстовых логов.

## Тесты и CI

Локальный smoke/unit gate:

```powershell
python -m pytest tests\unit_smoke -q
```

GitHub Actions запускает тот же smoke/unit gate для `main_branch` и pull
requests в `main_branch`.

## Known limits

- Это учебный/портфолио-проект, а не production trading software.
- Live-сценарии зависят от локальных сервисов и данных, которых может не быть в
  свежем checkout.
- Часть strategy/data деталей сознательно остается project-private.
- Крупные SQLite, bulk data, index и maintenance изменения требуют design
  review перед реализацией.
- Lint/type/coverage gates пока не входят в обязательный CI baseline.

## Roadmap

Ближайшая работа фиксируется в документах итераций. Текущие направления:

- поддерживать README и публичные факты проекта актуальными через README impact
  check при закрытии итераций;
- улучшить гигиену заметок и docs;
- повторить теорию и проектные решения для Junior+ readiness;
- превратить технический долг в приоритизированный backlog;
- решить, как отделять public infrastructure от private strategy logic.

