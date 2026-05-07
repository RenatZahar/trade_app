---
name: experiment-protocol
description: "Use for project experiments: experimental code, competing pipelines, temporary tables, data layout alternatives, performance hypotheses, architecture alternatives, or behavior-preserving optimizations. Requires a baseline and a durable record only when the experiment creates durable knowledge or changes project direction."
---

# Experiment Protocol

Keep experiments isolated, measurable, reversible, and documented without
turning small probes into full specs.

## Context Rule

Do not reread `AGENTS.md` or `docs/agent_context.md` if already loaded. Read the
concrete files, scripts, tests, logs, or metrics involved. Do not read old
experiment records unless the new experiment builds on them.

## When to Escalate

If the experiment touches SQLite, large data, indexes, maintenance scripts, or
long-running DB work, also use `$data-pipeline-safety-check`. Do not mutate data
until the user chooses a safe option.

## Experiment Record

Create or update `docs/experiments/<experiment-name>.md` only for durable
evidence, direction changes, data layout changes, runtime behavior changes, or
future reference. Use `docs/experiments/experiment_record_template.md` for the
detailed structure. For tiny probes, summarize in chat unless the user asks for
a file.

## Minimum Preflight

Before changing code or data, define goal/hypothesis, baseline command/result,
candidate approaches, scale tier, go/no-go criteria, rollback or cleanup plan,
and narrow verification.

Do not claim improvement without a baseline.

## Rules

- Keep behavior changes separate from performance comparisons unless approved.
- Mark temporary files, functions, tables, and flags as experimental.
- Keep competing experimental code out of production flow until a decision is recorded.
- Scale up only after correctness passes on a controlled slice.
- Before closing a durable experiment, record chosen/rejected options,
  validation, rollback status, debt, and cleanup.
