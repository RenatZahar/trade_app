# Parser Runtime Hardening - 2026-05-03

## Context

This work was started from live parser failures and noisy runtime logs:

- parser finished a block group and then failed with `'NoneType' object is not iterable`;
- parser logs contained terminal color escape sequences;
- Bitcoin Core memory grew sharply under large parser iterations;
- SQLite reported `database is locked` during overlapping parser runs;
- `vin` reconstruction warnings showed small gaps between expected input links and built negative records;
- parser throughput needed a practical `QUANTITY_OF_BLOCKS_IN_ITERATION` setting.

This record closes the immediate parser hardening pass and leaves the remaining larger architecture items explicit.

## What Changed

- Fixed parser stage finalization so non-empty block groups are not followed by a false `data_is_empty` stage finish.
- Guarded parser exception stage finishing when there is no active stage.
- Removed ANSI color escape sequences from parser log messages.
- Added parser cache runtime overrides:
  - `--parser-tx-cache-lines`;
  - `--parser-hash-cache-lines`.
- Made cache limit `0` mean disabled cache, including startup metadata and runtime behavior.
- Removed noisy price DataFrame tail output from logs.
- Moved parser cache settings into run metadata.
- Added structured parser timing logs through `modules/logger/timing.py`.
- Added live SQL-vs-BTC comparison support for explicit blocks:
  - `python main.py test downloaded-from-btc-data --blocks 873754,873755`.
- Added live missing-`vin` diagnostic test:
  - `MISSING_VIN_DIAGNOSTIC_BLOCKS=873243,873307 pytest tests/integration_live/test_missing_vin_diagnostics.py -q -s`.
- Hardened async JSON-RPC batch handling:
  - JSON-RPC item errors now stop the parser with a clear `RuntimeError`;
  - incomplete batch responses now stop the parser instead of silently dropping data.
- Fixed async RPC exception logging so traceback logging does not raise a second error.
- Registered the `integration_live` pytest marker.

## Why

The main goal was to make parser failures explicit and diagnosable before deeper optimization. The parser is a long-running data ingestion path, so silent partial data loss is worse than a failed run.

The chosen approach was intentionally conservative:

- keep SQLite writes ordered by group;
- do not introduce ordered async per-block saving yet;
- do not change Bitcoin Core architecture or ZMQ flow;
- add observability and fail-fast behavior around current RPC/data contracts.

## Findings

### Iteration Size

Live benchmark results:

- `QUANTITY_OF_BLOCKS_IN_ITERATION = 10` completed successfully:
  - 30 blocks in 240.8 seconds;
  - approximately 7.48 blocks/min.
- `20` was only slightly faster before failure:
  - approximately 8.33 blocks/min before the run failed;
  - Bitcoin Core reached roughly 19.6 GB working set / 21.8 GB private memory.
- `15` already showed overloaded RPC behavior:
  - `vout_rpc` tails around 99-349 seconds;
  - long active `getrawtransaction` queue in Bitcoin Core.

Decision: use `QUANTITY_OF_BLOCKS_IN_ITERATION = 10` for current production flow.

### Parser Cache

Disabling both parser caches is supported:

```powershell
python main.py --start_parser --parser-tx-cache-lines 0 --parser-hash-cache-lines 0
```

This reduces Python-side memory pressure. The main runtime bottleneck remains Bitcoin Core RPC, not pandas or local Python cache lookup.

### Missing `vin` Warnings

The live diagnostic checked blocks with visible warnings:

- `873243`: missing 44, all `prev_tx_is_coinbase`;
- `873307`: missing 34, all `prev_tx_is_coinbase`;
- `873774`: missing 65, all `prev_tx_is_coinbase`;
- `873846`: missing 9, all `prev_tx_is_coinbase`.

Conclusion: for the checked blocks, the small `vin` gaps are explained by spends of coinbase outputs. No `rpc_error`, `missing_vout_index`, or `prev_tx_not_returned` cases were found in this sample.

Mining-pool behavior may be useful as a separate feature family later, but it should not be mixed into the current ordinary wallet-flow contract without an explicit model decision.

### SQLite Writes

Current parser write behavior is intentionally conservative:

- process a group;
- build one DataFrame;
- save it;
- wait for save completion;
- move to the next group.

This avoids advancing the parser past unsaved blocks and keeps resume behavior simple. Ordered async per-block saving was rejected for now because it would significantly change parser contracts without a guaranteed performance win.

## Remaining Debt

- Add async RPC chunking and/or concurrency limits. `REQUESTS_QUANTITY` is currently used by sync RPC, while async RPC sends whole block-level batches.
- Decide whether no-address outputs should be:
  - excluded explicitly with diagnostics;
  - stored under a sentinel wallet id;
  - represented in a separate feature path.
- Add SQLite `busy_timeout` or a single-writer process policy to make concurrent writer failures clearer.
- Decide parser auto-restart policy after critical errors.
- Revisit parser/ZMQ flow only after parser lifecycle and idempotent rerun contracts are stable.

## Validation

- `python -m pytest tests\unit_smoke -q`
  - `71 passed`, one existing pandas deprecation warning.
- `MISSING_VIN_DIAGNOSTIC_BLOCKS=873243,873307,873774,873846 python -m pytest tests\integration_live\test_missing_vin_diagnostics.py -q -s`
  - `1 passed`.

## README Impact

README impact is deferred. This pass changes parser operational behavior and CLI flags, so README should later document:

- recommended parser cache override command;
- explicit block comparison mode;
- current recommended parser iteration size.
