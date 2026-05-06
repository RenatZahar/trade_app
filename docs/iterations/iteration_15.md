# Iteration 15 - Main pipeline collector contract and wallet_stats data collection

## Тема

Подготовка нового метода сбора данных для `main-pipeline` через общий collector
contract, с будущим переходом от legacy wallet chunk collection к варианту на
`data_table + wallet_stats`.

## Статус

Started on 2026-05-06.

Branch: `feature/iteration-15-collector-contract-wallet-stats`.

Start gate satisfied:

- iteration 14 is closed;
- `main_branch` and `origin/main_branch` were fast-forwarded to the iteration
  14 closing commit `cb11c3d`;
- this branch was created from that commit and pushed with upstream tracking.

## Дата планирования

2026-05-04

## Work Status

Current resume point:

- iteration 15 is open;
- Phase 1 design review selected the minimal safe path first;
- Phase 2-4 minimal implementation is in place: collector wrapper,
  `main-pipeline --collector legacy`, metadata/logging, and explicit
  `wallet-stats` stub;
- no SQLite schema, table data, indexes, bulk operations, or maintenance
  scripts should be changed as part of this minimal patch.

Decision:

- selected option: minimal patch;
- reason: it introduces the collector contract without changing SQL behavior;
- responsibility boundary: `collectors.py` owns collector selection and the
  collector request/result contract; `orchestrator.py` owns train/evaluate/save
  pipeline control; `data_operations.py` remains the legacy low-level
  SQL/Dask/dataframe implementation until it can be split safely;
- `training_entrypoints.py` remains the public training runtime API and now owns
  active model file discovery instead of leaving it in generic `service_funcs.py`;
- deferred: real `wallet_stats` table/collector implementation still requires
  a separate data safety design review before any DB mutation or expensive
  scan.

Checks:

- `python -m pytest tests\unit_smoke\test_main.py tests\unit_smoke\test_runtime_scenarios.py tests\unit_smoke\test_collectors.py tests\unit_smoke\test_training_entrypoints.py -q`
  passed: `29 passed`;
- `.venv\Scripts\python.exe -m pytest tests\unit_smoke -q` passed:
  `110 passed, 1 warning`;
- system `python -m pytest tests\unit_smoke -q` failed in
  `test_dependency_runtime_contracts.py` because the system Python has
  `dask_expr` installed while the project contract is verified in `.venv`.
- GitHub Actions `Quality Gate / Smoke/unit tests` failed on `main_branch`
  commit `cb11c3d` because `settings/data_operations.py` is ignored locally and
  missing in clean CI checkout; tracked code imports
  `settings.data_operations.MIN_TXS_PER_WALLET` and
  `TOTAL_AMOUNT_MORE_THAN_BTC`.
- Latest local verification after tracker cleanup:
  `.venv\Scripts\python.exe -m pytest tests\unit_smoke -q` passed:
  `110 passed, 1 warning`.
- Parser tracker cleanup:
  - `modules/blockchain_parser/main_parser.py` no longer manually starts and
    finishes tracker stages; it uses shared `tracked_stage(...)`;
  - `modules/blockchain_parser/parser_runtime.py` no longer manually finishes
    failed runs; it uses shared `finish_runtime_error(...)`;
  - `tracked_stage(...)` now accepts callable `success_details`, so stage
    details can be computed inside the stage without duplicating finish logic.
- Progress tracker cleanup:
  - `modules/logger/timing.py` now delegates stage progress logging to shared
    `log_runtime_progress(...)`;
  - local ignored `modules/teach_and_update_models/data_operations.py` uses the
    same helper instead of a private `get_current_run_tracker()` wrapper.

Next narrow step:

- fix the CI-only missing `settings.data_operations` boundary by moving needed
  constants into tracked config/code or removing the import if unused;
- then commit/push the scoped iteration 15 changes after reviewing staged scope,
  excluding pre-existing unrelated local files/artifacts.

Local worktree note at start:

- pre-existing unstaged local changes were present in
  `make_project_archive.py`, `modules/teach_and_update_models/orchestrator.py`,
  and untracked `data/models/trained_models/ElasticNet_*` artifacts;
- they were intentionally not staged, committed, or reverted during iteration
  start.

## Почему это отдельная итерация

В iteration 14 фокус - correctness текущего main ML pipeline:

- train/predict preprocessing;
- feature schema;
- timestamp filters;
- threshold contract;
- Dask compatibility;
- получить хотя бы один успешный full run как baseline.

Изменение алгоритма сбора данных - более крупная работа. Она затрагивает
SQLite, большие таблицы, Dask execution shape, temp artifacts и будущий
`param-grid`. Поэтому ее нельзя смешивать с текущей отладкой main pipeline:
иначе будет непонятно, что именно изменило поведение.

## Главная идея

Не плодить отдельные top-level сценарии вроде `main-pipeline-wallet-stats`.

Оставить один сценарий:

```bash
python main.py main-pipeline
```

А метод сбора данных переключать через collector parameter:

```bash
python main.py main-pipeline --collector legacy
python main.py main-pipeline --collector wallet-stats
```

Default должен остаться `legacy`, чтобы старый запуск продолжал работать.

## Контракт collector-а

Старый и новый collectors должны возвращать один и тот же downstream contract:

```text
collect_correlation_training_data(...)
-> cor_data_in_iteration_to_teach_df
-> cor_data_in_iteration_to_profit_test_df
```

Ожидаемая форма wrapper-а:

```python
def collect_correlation_training_data(
    collector_name,
    test,
    filter_params,
    correlation_type,
    tmps,
    chunk_size,
    seed=None,
):
    ...
```

## Почему выбран contract-based подход

- `orchestrator`, `clean_data`, train, predict и profit-test должны оставаться
  максимально стабильными.
- Новый метод сбора можно строить за тем же интерфейсом, не переписывая весь ML
  pipeline.
- Старый collector остается fallback, если новый путь окажется медленным,
  ошибочным или неполным.
- Git rollback недостаточен: generated data, temp Parquet, SQLite state, model
  artifacts и ignored/private `data_operations.py` не защищены обычным commit
  history.
- Один сценарий с параметром проще поддерживать, чем два расходящихся
  `main-pipeline` entrypoints.

## Контекст из текущего проекта

### Из active work plan

Сначала нужно получить один успешный full `main-pipeline` run с текущими
исправленными контрактами. Только после этого можно менять data collection.

Будущее направление:

- default `legacy` collector wraps current collection path;
- future `wallet-stats` collector returns the same train/profit-test DataFrame
  contract;
- CLI/config can later expose `main-pipeline --collector legacy|wallet-stats`;
- separate temp/model output dirs and `param-grid` integration are deferred
  until main pipeline collector contract is stable.

### Из future development backlog

Релевантные пункты:

- SQL performance review для пайплайна обучения моделей:
  - проверить фактически используемые индексы;
  - использовать `EXPLAIN QUERY PLAN` для ключевых SQL-этапов;
  - оценить составные индексы под реальные `WHERE`, `JOIN`, `ORDER BY`;
  - учитывать цену индексов для insert/update.
- Пересмотреть модель `data_table + few_tx_wallets`:
  - legacy physical split оказался дорогим maintenance pattern;
  - предпочтительная альтернатива: `data_table` хранит все строки, а
    `wallet_stats` хранит статистику и flags по кошелькам.
- `wallet_stats` candidate fields:
  - `Wallet_id`;
  - total row/tx count;
  - activity flags such as `is_low_tx`, `is_ready_for_training`, `is_dirty`;
  - potentially queue/status fields for incremental rebuild.
- Инкрементальный пересчет:
  - после загрузки новых блоков фиксировать затронутые `Wallet_id`;
  - пересчитывать статистику только по измененным кошелькам;
  - не запускать full `GROUP BY Wallet_id` по всей БД без отдельного design
    review.
- `block_height_block_time_map` decision:
  - сейчас это local parquet cache;
  - при переходе к `wallet_stats` нужно решить, остается ли это parquet cache,
    переносится ли в SQLite/service table, пересчитывается ли из `data_table`,
    или заменяется другим lookup layer.
- DB schema contract:
  - новые SQLite таблицы должны быть описаны в явном DB schema contract;
  - scenarios должны явно заявлять зависимость от новых таблиц.
- Stop/resume после переделки data-flow:
  - определить, какие шаги можно безопасно повторять;
  - какие artifacts можно переиспользовать;
  - что происходит при остановке после data collection, feature/correlation
    data, clean data, train, evaluate, save model.
- Не возвращать duplicate scenarios:
  - старые `main_pipeline` / `param_grid` debug paths не нужно возвращать, если
    поведение покрывается текущими командами.

## Data safety constraints

Эта итерация касается SQLite, больших таблиц, индексов и long-running data
operations. Перед реализацией `wallet-stats` collector нужен design review по
правилам `docs/maintenance_guidelines.md`.

Нельзя сразу делать:

- full `GROUP BY Wallet_id` по всей БД без принятого design review;
- массовые `INSERT`, `DELETE`, `UPDATE`;
- создание/пересоздание индексов;
- `VACUUM` / `ANALYZE`;
- миграции или service tables.

Read-only inspection допустим только дешевый:

- наличие таблиц;
- schema metadata;
- список индексов;
- small `LIMIT` samples;
- точечный `EXPLAIN QUERY PLAN`.

## Planned phases

### Phase 0 - Baseline gate

Условие входа:

- iteration 14 получила хотя бы один successful full `main-pipeline` run;
- run id, stage durations, key logs and output artifacts documented.

Почему:

- без успешного baseline нельзя понять, новый collector улучшил систему или
  просто изменил поведение.

### Phase 1 - Design review

Сравнить варианты:

- minimal patch: wrapper + `legacy` default only;
- set-based SQL / production-oriented: `wallet_stats` with indexed joins or
  `EXISTS`;
- workaround: keep legacy collector and only tune Dask settings;
- long-term architecture: incremental `wallet_stats` rebuild queue and explicit
  artifact/resume contract.

Для каждого варианта оценить:

- full scans;
- expensive `GROUP BY`;
- bulk writes;
- index impact;
- interruption/resume behavior;
- verification before/after;
- maintenance complexity.

### Phase 2 - Collector wrapper with legacy default

Добавить `collect_correlation_training_data(...)`.

`legacy` collector должен просто оборачивать текущий
`get_corelation_by_tmsp_df(...)`.

Ожидаемый результат:

- behavior не меняется;
- existing `python main.py main-pipeline` работает как раньше;
- metadata/logs фиксируют active collector.

### Phase 3 - CLI/config selector

Добавить collector selector:

```bash
python main.py main-pipeline --collector legacy
```

Default:

```text
legacy
```

Ожидаемый результат:

- старый способ запуска остается backward-compatible;
- новый параметр виден в run metadata.

### Phase 4 - wallet-stats stub

Добавить `wallet-stats` collector как explicit stub:

```text
collector wallet-stats is not implemented yet
```

Почему:

- проверяет CLI/config/control flow без изменения data collection;
- позволяет зафиксировать интерфейс до реализации.

### Phase 5 - wallet-stats design and implementation

Только после отдельного design review.

Возможная форма:

- `wallet_stats` table or view with `Wallet_id` and activity/training flags;
- collector filters candidate wallets through `wallet_stats`;
- transaction rows still come from `data_table`;
- avoid physical row movement between `data_table` and `few_tx_wallets`.

### Phase 6 - Contract comparison

Сравнить `legacy` и `wallet-stats` collectors:

- row counts train/profit;
- columns and dtypes;
- timestamp ranges;
- action distribution;
- feature columns after `clean_data`;
- model contract;
- prediction distribution;
- final profit-test output.

Сравнивать не только final profit.

### Phase 7 - Param grid follow-up

После стабилизации main pipeline:

- reuse the same collector contract in `param-grid`;
- do not change main pipeline and param grid collection logic in one step.

## What is intentionally deferred

- separate temp dirs per collector;
- separate model/profit output dirs per collector;
- param grid collector support;
- making `wallet-stats` the default collector;
- stop/resume implementation;
- full optimal-load Dask experiment after collection method changes.

## Definition of Done

- `main-pipeline` supports collector selection with default `legacy`.
- `legacy` collector preserves current behavior.
- `wallet-stats` path is either a clear stub or implemented after design review.
- Collector name appears in run metadata/logs.
- New SQLite tables, if any, are documented in DB schema contract.
- No destructive or expensive DB operation was added without design review.
- Old and new collectors can be compared through the same train/profit DataFrame
  contract.
- Param grid follow-up is documented if not implemented.
