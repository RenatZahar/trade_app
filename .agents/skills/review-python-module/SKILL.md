---
name: review-python-module
description: "Use when asked to review Python modules, patches, diffs, or tests without editing files. Focus on bugs, behavioral regressions, data-loss risks, incorrect error handling, weak boundaries, and missing tests. Findings must come first with file/line references."
---

# Review Python Module

Use this as a review-only workflow. Do not edit files unless the user explicitly changes the task from review to implementation.

## Scope Rule

Inspect only the requested file, patch, diff, and the nearest code/tests needed to validate behavior.

Do not expand into a broad architecture audit unless the user explicitly asks for it or a concrete finding requires checking a caller/callee contract.

## Review Focus

Prioritize:

- incorrect behavior;
- regressions against documented contracts;
- data-loss or data-corruption risks;
- swallowed exceptions or misleading success states;
- unsafe DB or filesystem side effects;
- weak module boundaries;
- missing tests for changed behavior;
- unnecessary complexity that creates concrete risk.

Do not lead with style nits. Mention style only when it hides a real bug or maintenance risk.

## Workflow

1. Read the requested file, patch, or diff.
2. Inspect nearby code and tests enough to validate behavior.
3. Report findings first, ordered by severity.
4. Use tight file/line references.
5. Add open questions only after findings.
6. Add a short summary only after findings and questions.

## Severity

- P0: data loss, security issue, broken core workflow, or change that should not ship.
- P1: likely bug, regression, or missing validation in important behavior.
- P2: maintainability or test gap with realistic future cost.
- P3: minor issue; include sparingly.

## Output

If issues exist, output findings first. If no issues are found, say that clearly and mention remaining test gaps or residual risk.

Keep output concise. Do not paste long code excerpts.
