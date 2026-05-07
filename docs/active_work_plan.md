<!-- docs/active_work_plan.md -->
# Active Work Plan

## Purpose

Current priorities only. Read `docs/agent_context.md` first; use this file only
when the task needs priority context beyond the active resume point.

Historical notes belong in iteration files or `docs/future_development_backlog.md`.

## Current State

As of 2026-05-06:

- Iteration 15 is active on branch `feature/iteration-15-collector-contract-wallet-stats`.
- Iteration 14 closed the main ML pipeline correctness baseline; the pipeline can complete, but the all-cash/no-buy profit-test result is not trusted model evidence.
- Runtime production references to the legacy `few_tx_wallets` / `TXS_MOVED` path were removed; historical docs may still mention them.
- The verified dependency stack is the project `.venv` / `requirements.lock.txt`.

## Active Priorities

### 1. Finish Iteration 15 Minimal Collector Contract

- Continue from `docs/iterations/iteration_15.md`, section `## Work Status`.
- Keep the minimal safe collector path unless the user changes scope.
- Do not implement real `wallet_stats` DB behavior without a separate data safety design review.
- Fix the clean-checkout `settings.data_operations` boundary before commit/push.

### 2. Make Profit-Test Results Trustworthy

- Explain the all-cash/no-buy result.
- Add or verify baseline comparisons: always cash, buy-and-hold, and simple price/trend baseline where practical.
- Report drawdown, exposure, turnover, trade count, profit factor, and PnL.
- Use several walk-forward windows before treating a result as evidence.

### 3. Verify Param-Grid And Performance Later

- Verify `python main.py param-grid` after pipeline contract fixes.
- Keep behavior-changing parameters separate from performance knobs.
- Tune Dask only after correctness is stable and baseline measurements exist.

## Deferred Or Future Work

- SQL performance review and data collection optimization.
- Legacy notebook vs current pipeline comparison.
- Feature audit and model signal review.
- Parser data contract for model use.
- Iteration 12 theory review.

Use `docs/future_development_backlog.md` only when one of these becomes active.

## Not Current Priority

- Actor/entity clustering for wallets.
- Full parser architecture rewrite or ZMQ parser replacement.
- Live trading execution and exchange order management.
- New model families before current evidence is trustworthy.
- Broad lint rollout across the old codebase.
