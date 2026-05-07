<!-- AGENTS.md -->
# Project Instructions

## Operating Principle

Use the smallest useful context first. Expand only when the task proves it needs
more.

## Entry Check

For any task that may edit files:

1. Run `git status -sb`.
2. Read `docs/agent_context.md` if present.
3. Read only files, tests, logs, or docs directly relevant to the request.
4. Do not revert, overwrite, or clean unrelated user changes unless explicitly requested.

## Context Routing

Open additional docs only by trigger:

- Iteration start/continue/close/merge: read `docs/active_work_plan.md` and the relevant `docs/iterations/iteration_<N>.md`, starting at `## Work Status`.
- Roadmap, learning plan, Junior+ process, portfolio framing: read `docs/junior_plus_program.md`.
- SQLite, large data, indexes, maintenance, `data_table`, `few_tx_wallets`, `wallet_stats`, `moving_txs`, `VACUUM`, `ANALYZE`, migrations, or long-running DB work: read `docs/maintenance_guidelines.md` and use `$data-pipeline-safety-check`.
- Experiments, competing approaches, performance hypotheses, temporary layouts, or experimental code: use `$experiment-protocol`.
- Logs or agent artifacts: read `summary.json` first, then targeted metadata or `events.jsonl` slices. Never read large logs end-to-end by default.
- README impact: check only when closing an iteration, when the user asks, or when user-facing behavior clearly changed.

`docs/*_translate_ru.md` files are explanatory user-facing notes, not primary
instructions. Do not read them by default. Update them only when the task
explicitly changes project instructions or docs.

## Task Routing

Use direct patch for narrow local tasks: typos, comments, log format, argparse
wording, small docs, small pure-function tests, or obvious targeted tests.

Use `$discuss-plan-execute` for substantial, ambiguous, architectural,
refactoring, research, multi-file, multi-phase, or high-risk work.

Use `$review-python-module` for review requests. Findings first; do not edit
files unless asked.

Use `$iteration-workflow` for starting, continuing, closing, merging, or creating
iterations.

Use `$iteration-handoff` when continuing in a new chat, updating Work Status, or
preserving state across context limits.

## Refactor Check

Before substantial restructuring, state a concise logic trace:

- caller responsibility;
- callee responsibility;
- duplicated or unclear responsibility;
- observable contract and narrow verification.

Skip this for new code, docs, log wording, argparse details, smoke tests, and
other narrow local changes.

## Cost Control

- Do not perform broad audits without explicit request.
- Search first, then open the smallest useful file slice.
- Do not inspect whole directories, long iteration histories, or large logs unless needed.
- Do not paste large logs or long code excerpts into responses.
- Keep docs and small fixes minimal.
- Suggest a new chat when context becomes long or scope changes materially.
- Write handoff into iteration docs only when the user agrees, asks for it, or the task is handoff work.
- Do not use web search when local project context is enough.

## Data Safety Hard Stop

For SQLite, large data, indexes, bulk DB changes, maintenance scripts, or
long-running DB work, do not implement the first working idea. Use
`$data-pipeline-safety-check`, present a design review, and wait for the user to
choose before mutation or expensive full scans. Cheap read-only metadata
inspection is allowed.

## Experiment Safety

Use `$experiment-protocol` for experiments. Create a durable record under
`docs/experiments/` only when the experiment changes direction, runtime behavior,
data layout, or future decisions. If it touches SQLite or large data, also use
`$data-pipeline-safety-check`.

## Validation

- Run the narrowest relevant tests after code changes.
- For broad runtime, CLI, logging, or ML pipeline changes, prefer `python -m pytest tests\unit_smoke -q`.
- Prefer `.venv` when docs or Work Status say system Python differs from the verified runtime.
- If tests are not run, state why and the residual risk.

## Do Not

- Do not edit `.env` or secrets.
- Do not rewrite large files when a scoped patch is enough.
- Do not introduce new architecture without explaining the tradeoff.
- Do not merge experimental code into production without a recorded decision.
- Do not turn small fixes into heavy proposal/spec ceremonies.
- Do not read or summarize large logs end-to-end when a summary or targeted slice exists.
