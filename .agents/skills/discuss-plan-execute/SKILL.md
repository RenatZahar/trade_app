---
name: discuss-plan-execute
description: "Use for substantial, ambiguous, research, architecture, refactoring, multi-file, multi-phase, or high-risk project work where Codex should first discuss context, risks, options, and a phased plan before editing. Do not use for tiny local fixes that can be safely patched directly."
---

# Discuss Plan Execute

Use this workflow to prevent premature coding on work that needs framing.

## Context Rule

Start with the smallest useful context. Do not reread `AGENTS.md` or
`docs/agent_context.md` if they are already in the session.

Usually enough:

1. `AGENTS.md`;
2. `docs/agent_context.md` if present;
3. files, tests, docs, or logs directly named by the user;
4. additional docs only when the task trigger requires them.

Do not inspect all of `docs/` by default.

## Workflow

1. Restate the goal, scope, and current understanding.
2. Identify risks, unknowns, and likely affected modules.
3. Offer a small phased plan.
4. Ask only blocking questions.
5. Make reasonable assumptions for non-risky details.
6. Execute only the agreed phase or the clearly safe next step.
7. After execution, summarize changed files and validation.

## Use Direct Patch Instead

Do not slow down small local tasks such as:

- typo fixes;
- log message formatting;
- argparse wording;
- documentation-only edits;
- small pure-function tests;
- local comments.

## Escalate to Safety Review

If the work touches SQLite, bulk data, indexes, maintenance scripts, or long-running data operations, use `$data-pipeline-safety-check` instead of ordinary planning.

## Output Shape

For the framing phase, return:

- goal;
- context learned;
- constraints;
- risks;
- plan;
- open questions or assumptions.

Keep the framing concise. Do not include long code excerpts or broad audit notes unless needed.

For execution, keep patches scoped and run the narrowest useful verification.
