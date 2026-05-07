---
name: iteration-workflow
description: "Use when starting, continuing, closing, merging, documenting, or creating project iterations in this repository. Covers iteration docs, branch checks, final notes, commit/push/merge flow, and creating the next iteration branch."
---

# Iteration Workflow

Keep project iterations consistent across chats and branches without broad
history reads.

## Required Context

Read only what is needed. Do not reread `AGENTS.md` or `docs/agent_context.md`
if already loaded. Usually: relevant iteration doc at `## Work Status`,
`git status -sb`, and current branch. Read `docs/active_work_plan.md` for
priority decisions. Read `docs/junior_plus_program.md` only for roadmap,
learning, new-iteration, or structure questions. Inspect recent commits only for
start/close/merge or branch diagnosis.

## Starting an Iteration

Confirm previous branch state, start from up-to-date `main_branch`, create a
`feature/iteration-<NN>-<topic>` branch, push it, and create/update the iteration
document with topic, goal, context, risks, chosen plan, DoD, and `## Work Status`.

## Continuing an Iteration

Confirm branch match when edits/commits are expected. Read `## Work Status`,
keep scope aligned with the iteration theme, record decisions only when useful
for future continuation, and run relevant checks after code changes.

## Closing an Iteration

Update final results, checks, warnings, and follow-up. Check README impact only
when requested, during closeout, or when public-facing facts changed. Run narrow
verification, review staged scope, commit, push, and merge/create next branch
only when requested or clearly part of closeout.

## Branch and Merge Rules

- Stable branch: `main_branch`.
- Iteration branch pattern: `feature/iteration-<NN>-<short-topic>`.
- Prefer fast-forward merge when the feature branch is directly ahead of `main_branch`.
- Do not delete or overwrite unrelated user changes.
- Do not push or merge if the staged scope includes unrelated work that the user did not approve.

## Output

Report active branch, iteration status, updated files, checks, and any
commit/push/merge/next-branch result. Keep it short unless closeout requires
details.
