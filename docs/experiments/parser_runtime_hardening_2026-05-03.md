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

### Run 90 Throughput Follow-Up

Run 90 was a longer live parser run on commit `e78b3bc`:

- run id: `90`;
- started at: `2026-05-03 18:49:48`;
- finished at: `2026-05-03 20:53:04`;
- status: `interrupted`;
- configured parser cache:
  - `max_lines_in_tx_cache=100000`;
  - `max_lines_in_hash_cache=0`;
- first requested block: `873883`;
- last completed saved range ended at: `874852`;
- completed successful groups: `97`;
- nominal completed group blocks: `970`;
- summed successful group wall-clock: `7321.97` seconds;
- nominal wall-clock throughput including saves: approximately `7.95` blocks/min.

The practical speed increase versus the earlier approximately `2.0` blocks/min one-block flow is about `4x`.

This was not caused by the timing decorators. The main reason is that the parser now runs with `QUANTITY_OF_BLOCKS_IN_ITERATION = 10`, so the existing `process_all_blocks()` concurrency actually works across multiple blocks and SQLite writes are amortized across a larger group. With `1` block per iteration, the same pipeline effectively waits for one block and then saves one block.

The log's rolling parser speed can show higher values, for example around `14` blocks/min, because those messages are based on cycle timing and do not always represent the full end-to-end wall-clock including save wait and run overhead. For operational planning, use stage `parser.process_blocks_group` wall-clock or run summary data.

Run 90 also exposed an existing data-contract issue: `get_transactions_of_blocks()` silently skips blocks where `len(block["tx"]) < 5`. In this run, the requested but absent SQL blocks were:

- `873893`, `3` transactions;
- `873904`, `1` transaction;
- `874540`, `1` transaction.

These blocks were absent from SQL because of the old small-block filter, not because of the new timing or JSON-RPC hardening. This should be fixed deliberately: either ingest these blocks normally or explicitly record them as intentionally excluded blocks. Silent skipping is not acceptable for a contiguous blockchain ingestion contract.

The explicit SQL-vs-BTC comparison was run on ten blocks across the completed run 90 range:

```powershell
python main.py test downloaded-from-btc-data --blocks 873991,874098,874206,874314,874421,874529,874637,874744,874852,873883
```

Result:

- run id: `92`;
- status: `success`;
- absent blocks: `0`;
- identical blocks: `8`;
- non-identical blocks: `2` (`874421`, `874852`);
- mismatch rows: `3` on each side.

The mismatches were float representation differences in `Amount`, for example `-0.01272107` versus `-0.012721070000000001`, with all identity columns matching. This does not look like data loss, but the comparison test should eventually use a numeric tolerance or integer satoshi representation for amount comparisons.

Other run 90 observations:

- no parser `ERROR`, `database is locked`, `NoneType`, or JSON-RPC item error was found in the log;
- run 90 ended by interruption, not by parser failure;
- `loaded_blocks < requested_blocks` appeared in three groups and was explained by the small-block filter above;
- `vin` gap warnings remained frequent: `128` warning lines, total gap `1039`, max gap `68`, max percentage `2.0983%`;
- based on earlier diagnostics, many small `vin` gaps can be coinbase-spend related, but run 90's higher max percentages deserve a broader diagnostic sample before treating all of them as harmless;
- timing logs are useful but verbose because every `PARSER_TIMING` line is also mirrored into tracker `stage_progress`.

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
