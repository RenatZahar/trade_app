---
name: iteration-handoff
description: "Use when continuing work in a new chat, creating or updating iteration Work Status, writing handoff context, resuming an in-progress iteration item, or reducing Codex context/cost while preserving project continuity."
---

# Iteration Handoff

Carry project work across chats without relying on long conversation history.

## Required Reads

Do not reread `AGENTS.md` or `docs/agent_context.md` if already loaded. Read the
requested iteration document at `## Work Status`. Read `docs/active_work_plan.md`
only when priorities are needed. Do not read old iterations unless the handoff
depends on them.

## Work Status Section

Use `## Work Status` as the primary resume point for new chats.

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

When continuing in a new chat, read `## Work Status` and continue the named item
or the only `in_progress` item. If several are `in_progress`, ask which one.
Avoid broad audits, whole-log reads, and web unless needed.

## Updating Handoff Context

Update Work Status only when the user agrees, asks for handoff, or important
state would otherwise be lost. Include latest run/log id, current decision or
error, files touched, tests run, next narrow step, and files/data not to touch.
Keep it concise; do not paste large logs.

## Coordination

- Use with `$iteration-workflow` for starting/closing/merging iterations.
- Use with `$discuss-plan-execute` for ambiguous refactors.
- Use with `$data-pipeline-safety-check` before risky SQLite or large-data mutations.
