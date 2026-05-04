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
  outcomes live in `docs/main_notes.md`, `docs/iterations/iteration_13.md`, and
  the cleaned project docs structure.
- Iteration `12 - Theory review and knowledge check` is intentionally deferred.
  It remains valuable, but it is time-consuming and should not block the current
  engineering work.
- Iteration `13 - Next development directions` is a backlog container for
  technical debt and architecture directions.
- Iteration `14 - ML pipeline correctness and trading validation` is the current
  main practical track.

## Current Priority Order

### 1. Keep Parser Backfill Stable

The blockchain parser is catching up historical blocks. Avoid changing parser
runtime behavior while a long run is healthy unless there is a clear failure or
data-loss risk.

Near-term parser follow-ups:

- classify or fix silent small-block exclusions;
- keep SQL-vs-BTC consistency checks available for sampled blocks;
- keep `vin` gap diagnostics as data quality evidence;
- treat parser throughput experiments as isolated experiments under
  `docs/experiments/`.

### 2. Fix Main ML Pipeline Correctness

This is the first active engineering priority from `iteration_14`.

Fix before trusting model results:

- train/predict preprocessing mismatch;
- accidental `index` feature leakage;
- timestamp filter parentheses and data alignment;
- `threshold` / `decision_threshold` config drift;
- feature schema contract for train and predict.

Expected validation:

- focused unit/smoke tests around the fixed contracts;
- rerun known model/profit-test scenarios only after these fixes.

### 3. Make Profit-Test Results Trustworthy

After ML contract fixes:

- add baseline comparisons: always cash, buy-and-hold, simple price-only/trend
  baseline where practical;
- include fees, spread/slippage, and execution delay at least in minimal form;
- report drawdown, exposure, turnover, trade count, profit factor, and PnL;
- run several walk-forward windows before treating a result as evidence.

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

- `docs/iterations/iteration_13.md`, especially SQL performance review and
  `data_table` / `wallet_stats` sections.

### 5. Compare Current Pipeline With Legacy Notebook Flow

Do this after the current pipeline is technically corrected enough to compare.

Goal:

- build a reproducible comparison path between the current app pipeline and the
  old notebook flow;
- save intermediate artifacts so differences are localized by step, not only by
  final output.

Relevant backlog:

- `docs/iterations/iteration_13.md`, section "Сравнение current pipeline и
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
