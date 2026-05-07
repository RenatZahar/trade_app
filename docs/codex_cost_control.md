<!-- docs/codex_cost_control.md -->
# Codex Cost Control

Status: human/reference note. Agents should not read this by default; the active
rules live in `AGENTS.md`, `docs/agent_context.md`, and relevant skills.

## Default Rule

Start small:

1. `AGENTS.md`;
2. `docs/agent_context.md`;
3. files, tests, logs, or docs directly needed for the task.

Search before opening whole files. Do not read old iterations, translated
rationale docs, large logs, generated artifacts, or backlog files unless the
task explicitly needs them.

## Expensive Context

Read more only when local inspection is insufficient, the task crosses module
boundaries, the user asks for architecture/refactor/debugging, or the work
touches SQLite, large data, indexes, maintenance, or experiments.

For `logs/agent_runs/<run_id>/`, use:

1. `summary.json`;
2. `manifest.json` only for metadata or artifact paths;
3. targeted `events.jsonl` slices by run_id, stage, timestamp, or error text.

## Handoff

Use `$iteration-handoff` when the user wants to continue in a new chat or when
important state would otherwise be lost. Write into iteration docs only when the
user agrees, asks for handoff, or the handoff itself is the task.

Short starter:

```text
Проект: I:\projects\trade_app_project.
Cost-control mode: read AGENTS.md and docs/agent_context.md first.
If continuing iteration 15, open docs/iterations/iteration_15.md at ## Work Status.
Do not broad-audit, read large logs end-to-end, or use web without need.
```
