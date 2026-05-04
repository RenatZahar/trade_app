# Iteration 13 - Parser backfill stability

## Тема

Стабильное догоняющее скачивание blockchain blocks без изменения рабочей логики
здорового parser run.

## Статус

Done with follow-ups

## Дата старта

2026-05-04

## Контекст

- Parser сейчас догоняет исторические блоки.
- После parser hardening текущая рабочая настройка:
  `QUANTITY_OF_BLOCKS_IN_ITERATION = 10`.
- Run 90 и run 94 показали кратный рост скорости относительно старого режима
  по одному блоку, но также показали операционные хвосты:
  small-block exclusions, `vin` gap warnings, verbose timing logs и заметное
  время SQLite save.
- Пока long parser run здоровый, приоритет - не ломать backfill ради
  преждевременной оптимизации.

## Цель итерации

Стабильно довести parser backfill до актуального blockchain tip или до
следующей явно зафиксированной остановки, сохранив возможность проверить
качество загруженных данных.

Итерация должна дать понятный operational status:

- сколько блоков догружено;
- какая фактическая скорость;
- какие предупреждения считаются понятными;
- какие data-quality вопросы нельзя игнорировать перед использованием данных в
  модели.

## Что входит в scope

### 1. Мониторинг здорового parser run

- Следить за текущим `run_id` и активным log-файлом с учетом log rotation.
- Использовать `parser.process_blocks_group` wall-clock как основную метрику
  скорости, а rolling parser speed считать вспомогательной.
- Фиксировать:
  - последний сохраненный блок;
  - примерную скорость blocks/min;
  - примерное ETA до blockchain tip;
  - ошибки `database is locked`, JSON-RPC item errors, `NoneType`, timeout/retry.

### 2. Data quality samples

- Периодически запускать SQL-vs-BTC comparison на конкретных sample-блоках,
  особенно после длинных uninterrupted run.
- Отдельно классифицировать:
  - float representation differences;
  - small-block exclusions;
  - `vin` gaps;
  - реальные missing rows, если они появятся.
- Не считать данные годными для ML только по факту отсутствия parser crash.

### 3. Small-block exclusions

- Зафиксировать проблему: старый parser path мог молча пропускать блоки, где
  `len(block["tx"]) < 5`.
- В этой итерации нужно принять минимальное решение:
  - либо ingest таких блоков как обычные;
  - либо явно записывать/документировать их как intentionally excluded.
- Silent skipping не должен оставаться неявным data contract.

### 4. `vin` gap diagnostics

- Использовать existing live diagnostic для выборочных блоков с warnings.
- Подтверждать, являются ли gaps coinbase-spend/no-address/service cases или
  реальной потерей данных.
- Не смешивать mining-pool/entity behavior в обычный wallet-flow contract без
  отдельного model decision.

### 5. Parser throughput experiments as deferred/isolated work

- Не менять production parser path во время здорового backfill.
- Если потребуется ускорение, оформлять это отдельным experiment record under
  `docs/experiments/`.
- Кандидаты на будущий эксперимент:
  - Bitcoin Core parser-only config profile;
  - `rpcthreads` / `rpcworkqueue` / `dbcache` sweep;
  - async RPC chunking/concurrency limits;
  - experimental `getblock` verbosity `2/3` path instead of many
    `getrawtransaction` calls.

## Риски

- Изменение parser runtime во время здорового backfill может создать новые
  data gaps или сломать resume behavior.
- Rolling speed может завышать реальную скорость, если не учитывать SQLite save
  и group wall-clock.
- `vin` gaps могут быть harmless в sample, но не должны автоматически считаться
  harmless на всем диапазоне.
- Small-block exclusions нарушают contiguous blockchain ingestion contract.

## Выбранный план

Работать консервативно:

1. Не менять здоровый parser run без причины.
2. Мониторить фактическую скорость и ошибки.
3. Делать sample consistency checks.
4. Зафиксировать или исправить small-block exclusion contract.
5. После завершения/остановки backfill записать итог в experiment/iteration docs.
6. Только после этого переходить к ML pipeline correctness.

## Definition of Done

- Зафиксирован итоговый диапазон догруженных блоков или причина остановки.
- Зафиксирована фактическая end-to-end скорость по stage wall-clock.
- Проверены sample-блоки через SQL-vs-BTC comparison.
- Small-block exclusion policy явно описана или исправлена.
- `vin` warnings имеют documented classification для проверенного sample.
- Оставшиеся parser performance идеи перенесены в isolated experiment backlog.
- README impact check выполнен перед закрытием итерации.

## Итоговый closeout

Дата closeout: 2026-05-04.

### Operational status

- Основной backfill run: `95`.
- Статус run: `interrupted` - parser был остановлен вручную.
- Время run: `2026-05-04 06:17:19` - `2026-05-04 13:45:26`.
- Длительность: `07:28:07`.
- На старте run было рассчитано `blocks_to_download=72127`.
- Успешно обработанные группы: `199` групп по `10` блоков.
- Успешно обработанный диапазон: `875683-877672`.
- Последний сохраненный блок в `data_table`: `877672`.
- Общая stage wall-clock скорость по успешным группам:
  `1990` blocks / `26814.23` sec = около `4.45` blocks/min.
- Скорость по последним 10 успешным группам:
  `100` blocks / `544.43` sec = около `11.02` blocks/min.
- Последние 10 успешных диапазонов:
  `877573-877582`, `877583-877592`, `877593-877602`,
  `877603-877612`, `877613-877622`, `877623-877632`,
  `877633-877642`, `877643-877652`, `877653-877662`,
  `877663-877672`.

Operational note:

- `logs/agent_runs/700/events.jsonl` не является реальным parser run. Это
  тестовый артефакт от `tests/unit_smoke/test_main_parser.py`, где run id
  подменяется на `700`; у него нет `manifest.json` и `summary.json`.

### SQL-vs-BTC sample check

Проверка выполнена через:

```bash
python main.py test downloaded-from-btc-data --blocks 877663,877668,877672
```

Результат run `96`:

- status: `success`;
- comparison_status: `all_blocks_identical`;
- requested_blocks: `877663`, `877668`, `877672`;
- sql_rows_count: `30053`;
- chain_rows_count: `30053`;
- identical_blocks_count: `3`;
- non_identical_blocks_count: `0`;
- diagnostics_rows_count: `0`;
- only_in_sql_rows_count: `0`;
- only_in_btc_rows_count: `0`.

Вывод: для проверенных sample-блоков SQL-данные совпали с независимой
BTC-реконструкцией. `vin` diagnostics не блокируют closeout, потому что в
проверенном sample diagnostics пустые.

### Small-block exclusion policy

В этой итерации принято консервативное решение:

- не добавлять fake rows в `data_table`;
- не создавать отдельную service-таблицу под факт попытки скачивания small
  blocks;
- считать small-block exclusions явным parser data contract для текущего
  production path;
- не менять runtime-поведение parser во время здорового backfill.

Причина: `data_table` хранит transaction/wallet rows, а не факт посещения
блока. Fake row исказила бы смысл таблицы, а новая service-сущность добавила бы
обязательство учитывать ее во всех downstream-контрактах.

Long-term follow-up: если понадобится строгий contiguous block-status contract,
проектировать его отдельно как service metadata / experiment, а не как
неявную строку в `data_table`.

### Parser performance ideas

Performance-идеи не внедрялись в production parser path в рамках closeout.
Они остаются isolated experiment backlog:

- Bitcoin Core parser-only config profile;
- `rpcthreads` / `rpcworkqueue` / `dbcache` sweep;
- async RPC chunking/concurrency limits;
- experimental `getblock` verbosity `2/3` path instead of many
  `getrawtransaction` calls.

Текущее production-решение остается `QUANTITY_OF_BLOCKS_IN_ITERATION = 10`.

### Parser progress logging

Перед финальным closeout добавлена краткая INFO-строка `PARSER_PROGRESS` после
каждой успешно сохраненной группы. Она показывает последний диапазон,
processed/remaining blocks, скорость по rolling window успешных групп и ETA.
Verbose `PARSER_TIMING` logs остаются для debug.

### README impact check

README impact: none.

Причина: closeout не менял публичные CLI-команды, runtime-сценарии,
env/config requirements, high-level architecture или documented quickstart.
Итерация зафиксировала operational status, sample data-quality result и
parser data-contract решение.

### Remaining follow-ups

- Если unit tests снова создают реальные `logs/agent_runs/*` артефакты,
  изолировать logger outputs в temp dir внутри тестов.
- При следующей parser остановке повторять narrow SQL-vs-BTC sample check на
  свежем хвосте диапазона.

## Out of scope

- Исправление main ML pipeline.
- Profit-test/backtest изменения.
- Оптимизация SQL data collection для обучения.
- Массовые SQLite maintenance операции.
- Полный parser rewrite или переход на ZMQ/getblock path без отдельного
  experiment protocol.

## Связанные документы

- `docs/active_work_plan.md`
- `docs/experiments/parser_runtime_hardening_2026-05-03.md`
- `docs/future_development_backlog.md`
