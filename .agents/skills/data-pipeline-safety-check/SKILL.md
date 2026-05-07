---
name: data-pipeline-safety-check
description: "Use before implementing or changing risky data work in this repo: SQLite, large tables, bulk INSERT/DELETE/UPDATE, indexes, VACUUM, ANALYZE, migrations, maintenance scripts, data_table, few_tx_wallets, wallet_stats, moving_txs, DB cleanup, or long-running operations. Produce a design review first; do not mutate data or implement risky changes until the user chooses an option."
---

# Data Pipeline Safety Check

Use this as a hard preflight for data operations that may be slow, destructive, difficult to resume, or expensive to verify.

## Required Reads

Read only the safety-relevant context first. Do not reread `AGENTS.md` or
`docs/agent_context.md` if they are already in the session.

Usually enough:

1. `AGENTS.md`;
2. `docs/agent_context.md` if present;
3. `docs/maintenance_guidelines.md`;
4. the concrete scripts/config/tests named by the task.

Do not read old experiment records or iteration histories unless they are directly needed for the proposed data change.

## Workflow

1. Identify the affected databases, tables, indexes, scripts, flags, settings, and generated artifacts.
2. Separate safe read-only inspection from risky mutation or expensive full scans.
3. Produce a design review before implementation.
4. Recommend one option and wait for the user to choose before risky implementation.

## Design Review Requirements

Compare 2-4 options:

- minimal patch;
- set-based SQL / production-oriented approach;
- workaround / maintenance approach;
- long-term architecture option when relevant.

For each option, state:

- operations performed;
- full scans and expensive `GROUP BY`;
- bulk `INSERT`, `DELETE`, or `UPDATE`;
- index creation, deletion, or rebuild;
- approximate runtime and data volume risk;
- interruption behavior;
- whether rerun/resume is safe;
- checks before and after;
- code and data maintenance cost.

## Project-Specific Rules

- Treat `moving_txs` as a legacy maintenance path.
- Prefer designing around `data_table + wallet_stats` over physically moving low-activity wallet rows between hot and cold tables.
- Treat `data_table` as the working table.
- Treat `few_tx_wallets` as cold storage unless a new design review changes that.
- Require indexes primarily for `data_table`.
- Run `VACUUM` before `ANALYZE` when both are part of a chosen maintenance plan.

## Safe Without Confirmation

Read-only inspection may proceed when it is cheap and non-mutating:

- checking file existence;
- reading config flags;
- listing tables and indexes;
- `SELECT 1 ... LIMIT 1`;
- small `PRAGMA` metadata queries.

Avoid full `COUNT(*)`, full-table `GROUP BY`, broad `quick_check`, or other expensive scans unless the user accepts the cost.

## Output

Return the design review first. Do not patch code, mutate databases, rebuild indexes, or launch maintenance commands until the user chooses an option.
