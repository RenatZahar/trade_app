# Project Instructions

## Context First

- Before non-trivial work, inspect `docs/` and the relevant files inside it.
- Treat `docs/active_work_plan.md` as the current short-term work selector:
  read it after `docs/junior_plus_program.md` to understand what is active,
  deferred, and next.
- Treat `docs/maintenance_guidelines.md` as the source of truth for SQLite, bulk data, index, and maintenance work.
- Treat `docs/junior_plus_program.md` and `docs/iterations/` as project process and roadmap context.
- Treat the `## Work Status` section inside the active iteration document as
  the primary resume point when continuing work across chats.
- Check `git status` before editing. Never revert or overwrite user changes unless explicitly requested.

## Instruction Priority

- `AGENTS.md` and active `.agents/skills/*/SKILL.md` files define agent behavior.
- `docs/*_translate_ru.md` files are user-facing explanations and rationale, not primary agent instructions.
- If a translate file conflicts with `AGENTS.md` or an active skill, follow the active instruction.
- When active instructions change, update related `*_translate_ru.md` files when practical.

## Task Modes

- Use a direct patch only for small local tasks: log formatting, argparse details, comments, pure-function tests, or documentation.
- Use discuss-plan-execute for substantial, ambiguous, architectural, refactoring, research, or multi-phase work.
- In discuss-plan-execute, first state the current understanding, risks, options, and phased plan. Implement only the selected or clearly safe phase.
- For review requests, use a review stance: findings first, grounded in file/line references, and do not edit files unless asked.

## Refactor Entry Check

- At the start of an iteration or substantial phase that may refactor existing
  code, first run a logic trace to identify useful intervention points before
  editing.
- The logic trace should state:
  - caller responsibility;
  - callee responsibility;
  - duplicated responsibility;
  - dead or unclear code;
  - observable contract and narrow verification.
- Use this for existing-code restructuring, simplifying old logic, moving
  responsibilities between functions, or removing suspected redundant code.
- Do not require this ceremony for clearly new code, smoke tests, technical
  documentation, log wording, argparse details, small pure-function tests, or
  other narrow local tasks where the responsibility boundary is already clear.

## Cost Control Mode

- For large tasks, first give a short plan and wait for confirmation unless the
  user explicitly asked to execute immediately.
- Do not perform broad audits without an explicit request.
- Do not read large logs end-to-end; first search by run_id, stage, error text,
  or timestamp and then read the smallest useful slice.
- Do not use web search when the question can be answered from local project
  context.
- For documentation and small fixes, keep diffs minimal.
- When the chat context becomes long or the task scope changes materially,
  suggest a new chat and write a short handoff summary into the active iteration
  document before continuing.

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

- Use `$experiment-protocol` when designing, running, comparing, documenting, or cleaning up experimental code, data layouts, competing pipelines, performance hypotheses, or architecture alternatives.
- Store experiment decision records under `docs/experiments/`.
- If an experiment touches SQLite, large data, indexes, maintenance scripts, or long-running DB work, also use `$data-pipeline-safety-check` and wait for the user to choose a safe option before mutation.

## Skills

- Use `$data-pipeline-safety-check` for risky SQLite, bulk data, index, and maintenance tasks.
- Use `$discuss-plan-execute` for substantial or ambiguous work that should be framed before editing.
- Use `$review-python-module` when asked to review Python code or patches without editing.
- Use `$iteration-workflow` when starting, continuing, closing, merging, or creating a project iteration.
- Use `$iteration-handoff` when continuing an iteration in a new chat, updating
  Work Status, writing handoff context, or reducing chat context/cost.
- Use `$experiment-protocol` when working with experiments, competing approaches, temporary experimental code, or performance hypotheses.
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
