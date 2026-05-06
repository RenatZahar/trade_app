# Active Work Plan

## Purpose

This is the short current-context file for agents and future chats.

Use it after `AGENTS.md` and `docs/junior_plus_program.md` to understand:

- what is already considered closed;
- what is active now;
- what is intentionally deferred;
- which documents contain the detailed backlog.

Keep this file concise. Detailed plans, investigation notes, and historical
records belong in iteration files or `docs/future_development_backlog.md`.

## Current State

As of 2026-05-06:

- Iterations `1-10` are treated as completed foundation work.
- Iteration `11 - Notes and docs hygiene` is treated as closed. Its useful
  outcomes live in `docs/main_notes.md`, `docs/future_development_backlog.md`,
  and the cleaned project docs structure.
- Iteration `12 - Theory review and knowledge check` is intentionally deferred.
  It remains valuable, but should not block the current engineering work.
- Iteration `13 - Parser backfill stability` is closed as `Done with
  follow-ups`. Parser run `95` was stopped manually after successfully
  processing `875683-877672`; run `96` verified sample blocks `877663`,
  `877668`, and `877672` through SQL-vs-BTC comparison with
  `all_blocks_identical`.
- Iteration `14 - Main ML pipeline correctness` is closed on branch
  `feature/iteration-14-main-pipeline-correctness`.
- During iteration 14 the project `.venv` was upgraded to the verified
  Python `3.12.2` dependency stack recorded in `requirements.lock.txt`.
  Dask/distributed are now `2026.3.0`; Dask dataframe query-planning is enabled
  for Dask `2025+` because the legacy dataframe backend is no longer supported.
- Iteration 14 has achieved the main compatibility gate: a full
  `main-pipeline` run completed successfully after the Dask `merge_asof`
  parquet checkpoint changes.
- The latest successful full run reached profit-test, but model quality is not
  trusted yet: the observed result was all-cash/no-buy behavior.
- Runtime production references to the legacy `few_tx_wallets` / `TXS_MOVED`
  path have been removed. Historical experiment docs can still mention them.
- Iteration `15 - Main pipeline collector contract and wallet_stats data
  collection` is planned in `docs/iterations/iteration_15.md`. Its start gate
  is satisfied, but it has not been started in this worktree.
- Cost-control rules for long Codex sessions are recorded in
  `docs/codex_cost_control.md`. Prefer new-chat handoffs for each major phase.

## Active Priorities

### 1. Choose The Next Workstream

Iteration 14 is closed. The next workstream should be selected explicitly
instead of continuing to add scope to the closed correctness iteration.

Good next candidates:

- profit-test trustworthiness and no-buy/all-cash diagnosis;
- `param-grid` viability and cache/artifact contract;
- Dask performance ladder;
- iteration 15 collector/wallet_stats design.

Closed inside iteration 14:

- train/predict preprocessing contract fixes;
- accidental `index` feature leakage cleanup;
- timestamp filter and feature schema contract work;
- Dask `merge_asof` compatibility via parquet checkpoint;
- cost-control and Work Status handoff workflow;
- removal of active production references to `few_tx_wallets` / `TXS_MOVED`.

### 2. Make Profit-Test Results Trustworthy

The pipeline can complete, but the output is not yet model evidence.

Next checks:

- explain the all-cash/no-buy profit-test result;
- log and review wallet counts after behavioral filters;
- add or verify baseline comparisons: always cash, buy-and-hold, and a simple
  price-only/trend baseline where practical;
- report drawdown, exposure, turnover, trade count, profit factor, and PnL;
- run several walk-forward windows before treating a result as evidence.

### 3. Verify and Optimize Param-Grid

Detailed backlog: `docs/future_development_backlog.md`, section
`1.2 Проверка и оптимизация param-grid`.

Goals:

- verify that `python main.py param-grid` still works after the pipeline fixes;
- separate behavior-changing parameters from performance knobs;
- decide which intermediate artifacts should be cached for repeated grid runs;
- make cache keys include all parameters that change labels, features, filters,
  or train/profit windows.

### 4. Tune Dask and Pipeline Performance

Do this only after correctness is stable for the run being measured.

Current next planned trial:

- `24GB / 4 workers / 2 threads`;
- `chunk_size=150`;
- compare against the latest successful baseline before changing more knobs.

Performance knobs should not be treated as param-grid model parameters unless
they are proven to change the math.

### 5. Keep Parser Backfill Stable

Parser backfill stability is closed enough to move on, but remains an
operational follow-up when parser runs resume.

Near-term parser follow-ups:

- classify or fix silent small-block exclusions;
- keep SQL-vs-BTC consistency checks available for sampled blocks;
- keep `vin` gap diagnostics as data quality evidence;
- treat parser throughput experiments as isolated experiments under
  `docs/experiments/`.

## Deferred Or Future Work

- Iteration 15 collector contract and `wallet_stats` data collection design.
- SQL performance review and data collection optimization.
- Legacy notebook vs current pipeline comparison.
- Feature audit and model signal review.
- Parser data contract for model use.
- Iteration 12 theory review.

Use `docs/future_development_backlog.md` for these topics until one becomes the
active iteration or workstream.

## Not Current Priority

- Actor/entity clustering for wallets.
- Full parser architecture rewrite or ZMQ parser replacement.
- Live trading execution and exchange order management.
- New model families before the current pipeline contract and profit-test
  evidence are trustworthy.
- Broad lint rollout across the old codebase.

## How Agents Should Use This

When a new task starts:

1. Read `AGENTS.md`.
2. Read `docs/junior_plus_program.md`.
3. Read this file.
4. Use the active iteration document's `## Work Status` section as the primary
   resume point.
5. If the task touches SQLite, large data, indexes, or maintenance scripts,
   follow `docs/maintenance_guidelines.md` and the project data safety rules.
6. If the task is experimental, create or update an experiment record under
   `docs/experiments/`.
