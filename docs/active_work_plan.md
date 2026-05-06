# Active Work Plan

## Purpose

This document is the short current-context file for agents and future chats.

Use it after `AGENTS.md` and `docs/junior_plus_program.md` to quickly understand:

- what is already considered closed;
- what is intentionally deferred;
- what should be worked on next;
- which iteration documents contain the detailed backlog.

## Current State

As of 2026-05-04:

- Iterations `1-10` are treated as completed foundation work.
- Iteration `11 - Notes and docs hygiene` is treated as closed. The separate
  detailed iteration file is not part of the current docs set; its useful
  outcomes live in `docs/main_notes.md`, `docs/future_development_backlog.md`,
  and the cleaned project docs structure.
- Iteration `12 - Theory review and knowledge check` is intentionally deferred.
  It remains valuable, but it is time-consuming and should not block the current
  engineering work.
- `docs/future_development_backlog.md` is the backlog container for technical
  debt and architecture directions. It was intentionally moved out of
  `docs/iterations/` because it is a plan, not a closeable iteration.
- Iteration `13 - Parser backfill stability` is closed as `Done with follow-ups`.
  Parser run `95` was stopped manually after successfully processing
  `875683-877672`; run `96` verified sample blocks `877663`, `877668`, and
  `877672` through SQL-vs-BTC comparison with `all_blocks_identical`.
- Iteration `14 - Main ML pipeline correctness` is opened on branch
  `feature/iteration-14-main-pipeline-correctness`.
- During iteration 14 the project `.venv` was upgraded to the latest verified
  Python `3.12.2` dependency stack recorded in `requirements.lock.txt`.
  Dask/distributed are now `2026.3.0`; Dask dataframe query-planning is enabled
  for Dask `2025+` because the legacy dataframe backend is no longer supported
  by current Dask.
- Cost-control rules for long Codex sessions are recorded in
  `docs/codex_cost_control.md`. Prefer new-chat handoffs for each major phase
  instead of carrying a very long conversational context.
- After the dependency upgrade, scenario validation is still open. Use
  `scripts/run_main_pipeline_smoke.py --days 7` as a short compatibility check
  before repeating a full `main-pipeline` run, and validate other scenarios
  separately instead of treating `--start_parser` as a normal finite test.
- Iteration `15 - Main pipeline collector contract and wallet_stats data
  collection` is planned in `docs/iterations/iteration_15.md`, but should start
  only after iteration 14 gets at least one successful full `main-pipeline` run.
- The former broad ML/trading validation scope is kept in this file as the
  follow-up roadmap, not as a single oversized iteration.

## Current Priority Order

### 1. Keep Parser Backfill Stable

Parser backfill stability is closed enough to move on, but remains an
operational follow-up when parser runs resume. Avoid changing parser runtime
behavior while a long run is healthy unless there is a clear failure or
data-loss risk.

Near-term parser follow-ups:

- classify or fix silent small-block exclusions;
- keep SQL-vs-BTC consistency checks available for sampled blocks;
- keep `vin` gap diagnostics as data quality evidence;
- treat parser throughput experiments as isolated experiments under
  `docs/experiments/`.

### 2. Fix Main ML Pipeline Correctness

This is the active focused iteration after parser backfill stability closeout.
Detailed start document: `docs/iterations/iteration_14.md`.

Fix before trusting model results:

- train/predict preprocessing mismatch;
- accidental `index` feature leakage;
- timestamp filter parentheses and data alignment;
- `threshold` / `decision_threshold` config drift;
- feature schema contract for train and predict.

Expected validation:

- focused unit/smoke tests around the fixed contracts;
- rerun known model/profit-test scenarios only after these fixes.

Near-term collector direction:

- first get at least one successful full `main-pipeline` run with the current
  corrected contracts;
- detailed collector plan lives in `docs/iterations/iteration_15.md`;
- then introduce a collector contract instead of creating separate top-level
  scenarios:
  - default `legacy` collector wraps the current collection path;
  - future `wallet-stats` collector returns the same train/profit-test DataFrame
    contract;
  - CLI/config can later expose `main-pipeline --collector legacy|wallet-stats`;
- defer separate temp/model output dirs and param grid integration until the
  main pipeline collector contract is stable.

Detailed backlog from the earlier broad plan:

- Check and fix train/predict preprocessing:
  - training currently uses `StandardScaler().fit_transform(...)`;
  - profit-test can call `model.predict(...)` on raw features;
  - target shape is `sklearn Pipeline(StandardScaler(), ElasticNet())` or
    saving/applying the same scaler with the model.
- Remove accidental `index` from model features unless explicitly justified.
- Add feature schema contract:
  - model columns;
  - service columns;
  - missing/extra column behavior.
- Fix timestamp filters such as `Timestamp >= start & Timestamp <= end` by
  wrapping each condition in parentheses.
- Review `merge_asof(..., direction='nearest')` and decide whether explicit
  tolerance or `calculate_in_10_min_period` is required.
- Confirm train/test windows do not overlap through labels or derived
  artifacts.
- Decide the target contract: `Action` {-1, 0, 1}, future return, signal score,
  or another target.
- Verify regression on `Action` is the right model shape or compare with
  classifier/ranking/regime detector alternatives.

### 3. Make Profit-Test Results Trustworthy

After ML contract fixes:

- add baseline comparisons: always cash, buy-and-hold, simple price-only/trend
  baseline where practical;
- include fees, spread/slippage, and execution delay at least in minimal form;
- report drawdown, exposure, turnover, trade count, profit factor, and PnL;
- run several walk-forward windows before treating a result as evidence.

Detailed backlog from the earlier broad plan:

- Check that `Predicted_Action` creates real trading behavior and not a hidden
  all-cash mode.
- Report max drawdown, exposure, turnover, trade count, profit factor, PnL and
  baseline comparisons.
- Run at least 5 walk-forward windows, preferably 5-10, before trusting a
  result.
- Mark older `7%` / `17%` results as legacy/unverified until reproduced under
  the corrected protocol.

### 3.1 Feature Audit and Model Signal Review

Do this after the correctness and profit-test contract are fixed.

Backlog:

- Audit weighted buy/sell correlations, anti-correlations, `SASI-SABI`,
  `BABI-BASI`, EWM/CMLTV variants.
- Run ablation:
  - without `index`;
  - only raw weighted correlations;
  - only CMLTV/EWM features;
  - without suspicious or unstable features.
- Check coefficient/feature importance stability across windows.
- Decide whether to add OHLCV, volatility regime, funding, open interest,
  order book, exchange flow, or entity-level enrichment.

### 3.2 Parser Data Contract for Model Use

This connects parser data quality to ML trust.

Backlog:

- Make model pipeline aware of parser exclusions:
  - coinbase transactions;
  - no-address prev outputs;
  - outputs below `MIN_VALUE_THRESHOLD`;
  - intentionally excluded small blocks, if any.
- Keep SQL-vs-BTC consistency checks as evidence before model retraining.
- Do not start bulk data repair or backfill migrations without the SQLite/data
  safety design review.

### 4. Optimize DB Data Collection

Do this after the ML data contract is clearer, because query optimization should
target the actual required access pattern.

This work touches SQLite and large data, so it must follow the data safety
protocol:

- first produce a design review;
- compare minimal patch, set-based SQL, workaround/maintenance approach, and
  long-term architecture;
- evaluate indexes, interruption/resume behavior, verification before/after,
  and data-loss risk;
- do not run broad full-table scans or bulk updates without explicit approval.

Relevant backlog:

- `docs/future_development_backlog.md`, especially SQL performance review and
  `data_table` / `wallet_stats` sections.

### 5. Compare Current Pipeline With Legacy Notebook Flow

Do this after the current pipeline is technically corrected enough to compare.

Goal:

- build a reproducible comparison path between the current app pipeline and the
  old notebook flow;
- save intermediate artifacts so differences are localized by step, not only by
  final output.

Relevant backlog:

- `docs/future_development_backlog.md`, section "Сравнение current pipeline и
  legacy notebook pipeline".

### 6. Return to Theory Review

Iteration 12 should be resumed when there is a good pause in engineering work.

It is not canceled. It is deferred so the project can first address the current
runtime/model/data issues.

## Not Current Priority

- Actor/entity clustering for wallets.
- Full parser architecture rewrite or ZMQ parser replacement.
- Live trading execution and exchange order management.
- New model families before the current pipeline contract is corrected.
- Broad lint rollout across the old codebase.

## How Agents Should Use This

When a new task starts:

1. Read `AGENTS.md`.
2. Read `docs/junior_plus_program.md`.
3. Read this file.
4. If the task touches SQLite, large data, indexes, or maintenance scripts,
   follow `docs/maintenance_guidelines.md` and the project data safety rules.
5. If the task is experimental, create or update an experiment record under
   `docs/experiments/`.
