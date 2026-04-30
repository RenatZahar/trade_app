---
name: discuss-plan-execute
description: "Use for substantial, ambiguous, research, architecture, refactoring, multi-file, multi-phase, or high-risk project work where Codex should first discuss context, risks, options, and a phased plan before editing. Do not use for tiny local fixes that can be safely patched directly."
---

# Discuss Plan Execute

Use this workflow to prevent premature coding on work that needs framing.

## Workflow

1. Inspect `docs/`, current branch, and relevant files.
2. Restate the goal, scope, and current understanding.
3. Identify risks, unknowns, and likely affected modules.
4. Offer a small phased plan.
5. Ask only blocking questions. Make reasonable assumptions for non-risky details.
6. Execute only the agreed phase or the clearly safe next step.
7. After execution, summarize changes and validation.

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

For execution, keep patches scoped and run the narrowest useful verification.
