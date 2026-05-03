---
name: iteration-workflow
description: "Use when starting, continuing, closing, merging, documenting, or creating project iterations in this repository. Covers docs/iterations, docs/junior_plus_program.md, branch checks, iteration DoD, final notes, commit/push/merge flow, and creating the next iteration branch."
---

# Iteration Workflow

Use this skill to keep project iterations consistent across chats and branches.

## Required Context

Read:

- `docs/junior_plus_program.md`;
- relevant `docs/iterations/iteration_<N>.md`;
- `AGENTS.md`;
- `git status -sb`;
- current branch and recent commits.

## Starting an Iteration

1. Confirm the previous iteration branch is pushed.
2. Confirm the previous iteration is merged into `main_branch` locally and on origin.
3. Start from up-to-date `main_branch`.
4. Create a feature branch named like `feature/iteration-07-module-responsibility-boundaries`.
5. Push the new branch with upstream tracking.
6. Create or update the iteration document with:
   - topic;
   - goal;
   - context;
   - risks;
   - options;
   - chosen plan;
   - DoD.

## Continuing an Iteration

1. Confirm current branch matches the active iteration.
2. Read the active iteration document before implementation.
3. Keep scope aligned with the iteration theme unless the user explicitly changes scope.
4. Record important decisions and deferred work in the iteration document.
5. Run relevant checks after code changes.

## Closing an Iteration

1. Update the iteration document with final results, checks, known warnings, and remaining follow-up.
2. Run a README impact check before the final commit:
   - check whether the iteration changed public-facing project facts such as CLI commands, runtime scenarios, env/config requirements, logs/artifacts, tests/CI, high-level architecture, known limits, or roadmap;
   - if there is impact, update `README.md` in the same iteration before closing;
   - if there is no impact, record `README impact: none` in the iteration document;
   - if there is impact but README is intentionally deferred, record an explicit follow-up and do not treat the iteration as fully closed unless the user accepts the deferral.
3. Run the narrowest relevant verification. For broad runtime/CLI/logging/ML changes, use:
   - `python -m pytest tests\unit_smoke -q`
4. Check `git status -sb` and review the staged scope before committing.
5. Commit with a terse iteration-focused message.
6. Push the feature branch.
7. Merge into `main_branch` only when requested or clearly part of the user's requested closeout.
8. Push `main_branch`.
9. Create and push the next iteration branch when requested.

## Branch and Merge Rules

- Stable branch: `main_branch`.
- Iteration branch pattern: `feature/iteration-<NN>-<short-topic>`.
- Prefer fast-forward merge when the feature branch is directly ahead of `main_branch`.
- Do not delete or overwrite unrelated user changes.
- Do not push or merge if the staged scope includes unrelated work that the user did not approve.

## Output

Report:

- active branch;
- iteration status;
- files updated;
- checks run;
- commit/push/merge result when performed;
- next branch when created.
