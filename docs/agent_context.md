<!-- docs/agent_context.md -->
# Agent Context

Shortest current-context file. Keep it small; put history in iteration docs,
experiment records, or runtime artifacts.

## Current Work

- Active iteration: `docs/iterations/iteration_15.md`.
- Branch: `feature/iteration-15-collector-contract-wallet-stats`.
- Theme: `main-pipeline` collector contract and future `wallet_stats` data collection.
- Selected path: `wallet-stats` collector behind the collector contract, with
  `data_table` as raw source of truth and `wallet_stats` as derived cache.
- Current `wallet_stats` design direction: set-based incremental rebuild by
  non-overlapping block chunks, then collector filters candidate wallets by
  train-window activity and correlation handles finer filtering.
- Clean-checkout boundary for ignored/private `data_operations.py` has been
  fixed locally by moving tracked imports to `settings.main_pipeline` and lazy
  imports.
- Next narrow step: continue iteration 15 from `## Work Status`; wait for
  parser backfill before treating `wallet_stats` as useful; do not resume the
  old per-wallet pilot rebuild.

## First Reads

- Default: `AGENTS.md`, this file, then task-named files only.
- Continue active iteration: open `docs/iterations/iteration_15.md` at `## Work Status`.
- Need current priorities: open `docs/active_work_plan.md`.
- SQLite / large data / indexes / maintenance: open `docs/maintenance_guidelines.md` and use `$data-pipeline-safety-check`.
- Roadmap / learning / iteration process: open `docs/junior_plus_program.md`.

## Verification

Fast baseline:

```powershell
python -m pytest tests\unit_smoke -q
```

Prefer `.venv` when dependency behavior matters.

## Boundaries

Do not touch without explicit request: `.env`, secrets, unrelated local changes,
generated model artifacts, large SQLite data files, or ignored/private files.

Real DB note:

- `idx_wallet_id_block_height` was created on `data_table` and took about
  `4405` seconds.
- A pilot `wallet_stats` rebuild was interrupted; derived tables may exist in
  `C:\blocks_sql_data\blocks_sql_data_db.db` with `last_rebuild_status=running`.
- Treat that pilot state as disposable. The next rebuild code resets
  `wallet_stats` when previous status is not `success`.

For `logs/agent_runs/<run_id>/`, read `summary.json` first, then targeted
metadata or `events.jsonl` slices only.

Update this file when active iteration, branch, resume point, or first-read
routing changes.
