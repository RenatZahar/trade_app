# Experiment: <name>

Status: draft

## Goal

## Hypothesis

## Baseline

- Git commit:
- Command:
- Input/data slice:
- Runtime:
- Output/metrics:
- Correctness signal:
- Relevant config/seed:
- Known warnings or limits:

## Scope

- Affected modules:
- Affected tables/indexes:
- Affected CLI flags/settings:
- Tests/checks:

## Candidate Approaches

### Option A: <name>

- Change:
- Expected benefit:
- Risks:
- Expensive operations:
- Resume/rollback:
- Verification:

### Option B: <name>

- Change:
- Expected benefit:
- Risks:
- Expensive operations:
- Resume/rollback:
- Verification:

## Data Scale Tiers

- Tiny:
- Medium:
- Full/live:

## Go / No-Go Criteria

- Correctness:
- Runtime:
- Maintainability:
- Recovery:

## Behavior vs Performance Separation

- Behavior-equivalence check:
- Performance measurement:

## Rollback / Recovery Plan

## Measurements

| Option | Scale | Command | Runtime | Correctness | Notes |
| --- | --- | --- | --- | --- | --- |

## Cleanup Gate

- [ ] Chosen code moved to production path.
- [ ] Obsolete `experimental*` files removed or documented.
- [ ] Obsolete `experimental_` tables removed or documented.
- [ ] Production path checked for accidental experimental dependencies.
- [ ] Tests/docs updated.

## Decision Record

- Chosen option:
- Rejected options:
- Tradeoffs accepted:
- Validation performed:
- Remaining debt:
- Follow-up:
