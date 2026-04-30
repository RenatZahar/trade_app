# Experiment: moving_txs physical table split

Status: rejected / archived

## Goal

Проверить подход, при котором транзакции низкоактивных кошельков физически
переносятся из рабочей таблицы `data_table` в отдельную таблицу
`few_tx_wallets`, чтобы уменьшить объем горячих рабочих запросов.

## Hypothesis

Если вынести low-tx кошельки в холодную таблицу, основные запросы по
`data_table` станут легче, а обучение и аналитические выборки будут работать
быстрее.

## Baseline

- Git commit: исторический maintenance-путь до `iteration_07`.
- Command:
  - `python main.py --service move_txs`;
  - `python main.py --service move_txs_back`.
- Input/data slice: live SQLite DB with `data_table` and `few_tx_wallets`.
- Runtime: full/live maintenance could run for many hours.
- Correctness signal: rows end in the expected table, required indexes exist,
  `TXS_MOVED` matches the physical state, service tables are cleaned.
- Known warnings or limits: expensive full-table planning, bulk row movement,
  interruption/recovery complexity, `VACUUM` / `ANALYZE` cost.

## What The Functions Did

`move_txs` was the forward physical split:

- identify wallets whose transaction count made them low-activity;
- create/maintain service planning tables for the move;
- move rows for those wallets from `data_table` to `few_tx_wallets`;
- manage indexes and service state around the move;
- update `TXS_MOVED` after the operation;
- clean service tables after successful completion.

`move_txs_back` was the recovery/reversal path:

- return rows from `few_tx_wallets` back into `data_table`;
- clean `few_tx_wallets` after the return;
- remove `move_txs` service tables;
- restore required `data_table` indexes;
- run `VACUUM` and then `ANALYZE` when requested;
- update `TXS_MOVED` to `False`.

## Decision

The physical table split is rejected as a production direction.

Reasons:

- too much operational risk for live-scale SQLite maintenance;
- expensive bulk `INSERT` / `DELETE` / index / `VACUUM` work;
- difficult interruption and resume behavior;
- high verification cost on large tables;
- the optimization couples data layout to a maintenance script instead of a
  queryable wallet classification model.

## Chosen Direction

Do not expose `move_txs` / `move_txs_back` as user-facing CLI scenarios.

Future low-tx handling should be designed around:

- `data_table` as the working table;
- `wallet_stats` or equivalent classification metadata;
- query filters / joins / indexes that avoid physical row movement;
- explicit design review before any full/live data mutation.

## Cleanup Record

- `iteration_06` completed `move_txs_back`: data was returned to `data_table`,
  service tables were removed, required indexes were present, and `TXS_MOVED`
  was `False`.
- `iteration_07` removes the `main.py` / `cli_args.py` entrypoint for
  `--service move_txs` and `--service move_txs_back`.
- `iteration_07` moves the underlying legacy module and its old helper tests out
  of the working code path:
  - `legacy_moving_txs.py`;
  - `legacy_test_moving_txs.py`.
- Reusable `data_table` index helpers were kept in production code as
  `modules/sql_funcs/data_table_indexes.py`, because runtime scenarios and
  smoke tests still depend on those checks.
