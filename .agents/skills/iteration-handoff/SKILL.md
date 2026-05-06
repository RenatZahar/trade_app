---
name: iteration-handoff
description: "Use when continuing work in a new chat, creating or updating iteration Work Status, writing handoff context, resuming an in-progress iteration item, or reducing Codex context/cost while preserving project continuity."
---

# Iteration Handoff

Use this skill to carry project work across chats without relying on long
conversation history.

## Required Reads

Read the smallest useful set:

- `AGENTS.md`;
- `docs/active_work_plan.md`;
- the requested `docs/iterations/iteration_<N>.md`;
- `docs/codex_cost_control.md` when cost/context reduction is relevant.

## Work Status Section

Each active iteration document should have a `## Work Status` section near the
top. Use it as the primary resume point for new chats.

Status values:

- `pending`: planned, not started;
- `in_progress`: current active item;
- `blocked`: needs user decision or external condition;
- `done`: completed and recorded;
- `deferred`: intentionally postponed.

Recommended item format:

```md
### WS-<iteration>-<NNN> - Short title

Status: in_progress

Goal:
- ...

Current context:
- ...

Next step:
- ...

Do not touch without confirmation:
- ...

Status notes:
- YYYY-MM-DD: ...
```

## Starting A New Chat

When the user asks to continue an iteration in a new chat:

1. Read the iteration document.
2. Find `## Work Status`.
3. Continue the `in_progress` item unless the user named another item.
4. If several items are `in_progress`, ask the user which one to continue.
5. Use cost-control mode: avoid broad audits, avoid whole-log reads, and avoid
   web unless needed.

## Updating Handoff Context

Before ending a long chat or switching phase:

1. Update the relevant Work Status item.
2. Include the latest run/log id, current error, files touched, tests run, and
   the next narrow step.
3. Mark completed items `done`.
4. Keep handoff concise; do not paste large logs.

## Coordination

- Use with `$iteration-workflow` for starting/closing/merging iterations.
- Use with `$discuss-plan-execute` for ambiguous refactors.
- Use with `$data-pipeline-safety-check` before risky SQLite or large-data
  mutations.
