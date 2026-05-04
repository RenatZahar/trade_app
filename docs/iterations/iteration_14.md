# Iteration 14 - Parser backfill stability

## Тема

Стабильное догоняющее скачивание blockchain blocks без изменения рабочей логики
здорового parser run.

## Статус

Active

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
- `docs/iterations/iteration_13.md`
