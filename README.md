# trade_app

[Russian version](README.ru.md)

`trade_app` is a learning-oriented engineering project around Bitcoin data,
trading research, ML pipeline orchestration, and runtime reliability.

The main value of the repository is not a ready-to-use trading product. It is
an evolving example of how a data/ML project can be made more reproducible,
observable, testable, and understandable over time.

## Engineering Focus

This project is developed through documented Junior+ engineering iterations.
The current focus is on:

- reproducible runtime entrypoints;
- explicit configuration and runtime dependency contracts;
- structured logging and run tracking;
- machine-readable agent artifacts;
- smoke/unit tests and a minimal GitHub Actions quality gate;
- keeping architecture and operational limits explainable.

The iteration notes live in [`docs/iterations`](docs/iterations).

## Architecture

High-level flow:

```text
main.py
  -> cli_args.py
  -> runtime_scenarios.py
  -> modules/*
  -> logs/ and data artifacts
```

Important areas:

- `main.py` - unified local entrypoint.
- `cli_args.py` - CLI scenario parsing and validation.
- `runtime_scenarios.py` - orchestration layer for runtime scenarios.
- `settings/` - paths, runtime config, and dependency contracts.
- `modules/logger/` - text logs, run tracker, and agent-readable outputs.
- `tests/unit_smoke/` - fast contract/smoke checks.
- `.github/workflows/quality-gate.yml` - minimal CI quality gate.

## Quickstart

The safe baseline check does not require Bitcoin Core, Redis, Flask, or a live
database mutation.

```powershell
python -m pip install -r requirements.lock.txt
python -m pytest tests\unit_smoke -q
```

To inspect available runtime commands:

```powershell
python main.py --help
```

## Runtime Scenarios

The current CLI exposes:

```powershell
python main.py main-pipeline
python main.py param-grid --test-fraction 0.1 --seed 42
python main.py --start_parser
python main.py --start_parser --parser-tx-cache-lines 0 --parser-hash-cache-lines 0
python main.py test downloaded-from-btc-data 10 42
python main.py test downloaded-from-btc-data --blocks 873754,873755
```

These commands are live/runtime scenarios. They may require local services,
configured paths, and project data. The smoke test command above is the safer
first check for a fresh checkout.

`python main.py --start_parser` starts Bitcoin Core with the generated
`standard` profile config and restarts an already-running Core process when it
is not using that generated profile. The current standard parser profile is an
aggressive local backfill profile in [`settings/parser.py`](settings/parser.py);
larger values can overload local Bitcoin Core RPC before the Python pipeline
itself becomes the bottleneck.

## Runtime Dependencies

Runtime dependency contracts are defined in
[`settings/runtime_contracts.py`](settings/runtime_contracts.py).

Depending on the scenario, the project can require:

- SQLite data at `BLOCKS_SQL_DATA`;
- Redis;
- Bitcoin Core / Bitcoin RPC;
- Flask runtime;
- local price/model/data artifacts.

Example environment keys are listed in [`.env.example`](.env.example).
Do not commit real secrets or local credentials.

## Logs and Agent Artifacts

Runtime logging writes human-readable logs to:

```text
logs/<run_id>.log
```

Agent-readable artifacts are written to:

```text
logs/agent_runs/<run_id>/manifest.json
logs/agent_runs/<run_id>/events.jsonl
logs/agent_runs/<run_id>/summary.json
```

These artifacts are produced directly from the runtime tracker instead of
parsing text logs back into structured data.

## Tests and CI

Local smoke/unit gate:

```powershell
python -m pytest tests\unit_smoke -q
```

GitHub Actions runs the same smoke/unit gate on `main_branch` and pull requests
targeting `main_branch`.

## Known Limits

- This repository is a learning/portfolio project, not production trading
  software.
- Live scenarios depend on local services and data that are not guaranteed to
  exist in a fresh checkout.
- Some strategy/data details are intentionally treated as project-private.
- Broad SQLite, bulk data, index, and maintenance changes require a design
  review before implementation.
- Lint/type/coverage gates are not yet part of the mandatory CI baseline.

## Roadmap

Near-term work is tracked in the iteration documents. Current directions:

- keep README and public project facts synchronized through the README impact
  check at iteration closeout;
- improve notes/docs hygiene;
- review theory and project decisions for Junior+ readiness;
- turn technical debt into a prioritized backlog;
- decide how to separate public infrastructure from private strategy logic.
