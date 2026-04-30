# Project Instructions

## Context First

- Before non-trivial work, inspect `docs/` and the relevant files inside it.
- Treat `docs/maintenance_guidelines.md` as the source of truth for SQLite, bulk data, index, and maintenance work.
- Treat `docs/junior_plus_program.md` and `docs/iterations/` as project process and roadmap context.
- Check `git status` before editing. Never revert or overwrite user changes unless explicitly requested.

## Task Modes

- Use a direct patch only for small local tasks: log formatting, argparse details, comments, pure-function tests, or documentation.
- Use discuss-plan-execute for substantial, ambiguous, architectural, refactoring, research, or multi-phase work.
- In discuss-plan-execute, first state the current understanding, risks, options, and phased plan. Implement only the selected or clearly safe phase.
- For review requests, use a review stance: findings first, grounded in file/line references, and do not edit files unless asked.

## Hard Stop: Data and Maintenance Safety

- For tasks involving large data, SQLite, `data_table`, `few_tx_wallets`, `wallet_stats`, `moving_txs`, bulk `INSERT` / `DELETE` / `UPDATE`, indexes, `VACUUM`, `ANALYZE`, migrations, or long-running maintenance scripts, do not implement the first working idea immediately.
- First produce a design review comparing at least:
  - minimal patch;
  - set-based SQL / production-oriented approach;
  - workaround / maintenance approach;
  - long-term architecture option when relevant.
- Compare speed, data-loss risk, interruption/resume behavior, index impact, verification before/after, and maintenance complexity.
- Recommend one option, then wait for the user to choose before risky implementation.
- Read-only information gathering is allowed without confirmation when it does not mutate the database and does not require expensive full scans. Avoid full `COUNT(*)`, full-table `GROUP BY`, broad `quick_check`, or similar expensive scans unless the user accepts the cost.

## Experiment Protocol

- Mark temporary experiment entities clearly:
  - files or folders: `experimental*` or `experimental/`;
  - functions: `_experimental` suffix;
  - tables: `experimental_` prefix;
  - CLI flags: clear experimental wording.
- Keep competing experimental code out of production flow until the result is chosen.
- For each experiment, record goal, hypothesis, affected modules/tables/indexes, input size, command, timing, correctness checks, support cost, and final decision.
- After choosing an approach, move only the winning path into production, remove obsolete experimental code, and update docs.

## Skills

- Use `$data-pipeline-safety-check` for risky SQLite, bulk data, index, and maintenance tasks.
- Use `$discuss-plan-execute` for substantial or ambiguous work that should be framed before editing.
- Use `$review-python-module` when asked to review Python code or patches without editing.
- Do not let a meta-skill or retrospective rewrite project instructions automatically. Propose instruction changes and wait for explicit confirmation.

## Validation

- Run the narrowest relevant tests after code changes.
- For broad runtime, CLI, logging, or ML pipeline changes, prefer:
  - `python -m pytest tests\unit_smoke -q`
- If tests are not run, state why and describe the residual risk.

## Do Not

- Do not edit `.env` or secrets.
- Do not rewrite large files when a scoped patch is enough.
- Do not introduce new architecture without explaining the tradeoff.
- Do not merge experimental code into production without a recorded decision.
- Do not turn small local fixes into heavy proposal/spec ceremonies.
