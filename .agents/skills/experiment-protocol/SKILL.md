---
name: experiment-protocol
description: "Use when designing, running, comparing, documenting, or cleaning up project experiments: experimental code, competing pipelines, temporary tables, data layout alternatives, performance hypotheses, architecture alternatives, or behavior-preserving optimizations. Requires baseline, go/no-go criteria, scale tiers, rollback/recovery, cleanup gate, and a decision record under docs/experiments."
---

# Experiment Protocol

Use this skill to keep experiments isolated, measurable, reversible, and documented.

## When to Escalate

If the experiment touches SQLite, large data, indexes, maintenance scripts, `data_table`, `few_tx_wallets`, `wallet_stats`, `moving_txs`, `VACUUM`, `ANALYZE`, or long-running DB work, also use `$data-pipeline-safety-check`. Do not mutate data until the user chooses a safe option.

## Experiment Record

Create or update a decision record under:

```text
docs/experiments/<experiment-name>.md
```

Use `docs/experiments/experiment_record_template.md` as the starting structure when useful.

## Required Preflight

Before implementation, define:

- goal;
- hypothesis;
- current baseline;
- affected modules, tables, indexes, CLI flags, settings, and tests;
- candidate approaches;
- data scale tiers;
- go/no-go criteria;
- rollback or recovery plan;
- verification commands;
- cleanup plan.

## Baseline

Record current behavior before changing it:

- command;
- input size or data slice;
- runtime;
- output or metrics;
- correctness signal;
- git commit;
- relevant config and seed;
- known warnings or limits.

Without a baseline, do not claim an improvement.

## Behavior vs Performance

Do not mix behavior changes and performance changes in the same comparison unless the experiment is explicitly about behavior.

Preferred sequence:

1. Prove behavior equivalence on a small controlled slice.
2. Measure performance on the same behavior.
3. Scale up only after correctness checks pass.

## Data Scale Tiers

Use explicit tiers when data size matters:

- `tiny`: fast local sanity sample;
- `medium`: realistic enough to expose query/index behavior;
- `full/live`: production-sized or real data run.

Do not generalize full-data conclusions from `tiny` alone.

## Experimental Isolation

Mark temporary entities clearly:

- files or folders: `experimental*` or `experimental/`;
- functions: `_experimental` suffix;
- tables: `experimental_` prefix;
- CLI flags: clear experimental wording.

Keep competing experimental code out of production flow until a decision is recorded.

## Comparison

For each candidate approach, record:

- what changes;
- what stays behavior-equivalent;
- runtime and data volume;
- expensive operations;
- correctness checks;
- operational risks;
- support and maintenance cost;
- interruption/resume behavior;
- impact on production code.

## Cleanup Gate

Before closing the experiment:

- move only the chosen approach into production;
- remove obsolete experimental code and tables;
- verify no `experimental_*` remains in production path unless explicitly documented;
- update tests and docs;
- record unresolved technical debt.

## Decision Record

End with:

- chosen option;
- rejected options and why;
- tradeoffs accepted;
- validation performed;
- rollback/recovery status;
- remaining debt;
- follow-up tasks.

Do not present an experiment as complete without this decision record.
