# Experiment: main pipeline Dask load tuning

Status: active after one successful bounded smoke; waiting for full/live run result

Important caveat:

- This experiment plan was created before changing the main data collection
  method.
- The load rules below are valid only for the current/old collection method:
  SQLite wallet chunks -> pandas processing -> temporary Parquet -> Dask
  read/merge/sort.
- After the collection method is changed, these tuning assumptions may become
  obsolete.
- Expected next workflow:
  1. change the data collection method separately;
  2. run `main-pipeline` again and observe the new behavior;
  3. restart the optimal-load experiment from a fresh baseline.

## Goal

Find a stable and reasonably fast Dask load profile for
`python main.py main-pipeline`, especially the `process_chunk` phase in
`features.correlation_data`.

## Hypothesis

The current pipeline is dominated by pandas-heavy SQLite chunk extraction,
correlation calculation, Parquet writes, and later Dask merge/sort work.

Stability should improve when each worker runs fewer simultaneous tasks and each
task loads fewer wallets. Speed can then be recovered gradually by increasing
only one load parameter at a time.

## Baseline

- Git commit: `eeed41f91fa5a4fd97c17bfaccf7793eb69c6215` plus local/private
  iteration 14 patches.
- Command:

  ```bash
  C:\Users\renat\AppData\Local\Programs\Python\Python312\python.exe main.py main-pipeline
  ```

- Input/data slice: full/live model JSON `data/models/new_models/model copy 5.json`.
- Runtime:
  - run `105`: failed after `00:45:38`;
  - run `107`: running under medium profile at the time this experiment record
    was created;
  - performance tuning paused before applying `chunk_size=120` because the
    current priority changed to getting one successful full pipeline run.
- Output/metrics:
  - run `105` passed the `Unsupported correlation_type: 0.2` issue and failed
    on Dask DataFrame class compatibility;
  - run after medium profile showed low managed memory on the dashboard during
    `process_chunk`.
- Correctness signal:
  - unit smoke after local fixes: `84 passed, 1 warning`;
  - full pipeline not yet completed under corrected contracts.
- Relevant config/seed:
  - seed: `null`;
  - current medium profile before next-step tuning:
    `total_memory='24GB'`, `n_workers=2`, `threads_per_worker=2`,
    `chunk_size=90`.
- Known warnings or limits:
  - Dask unmanaged-memory warnings appeared on the previous `7.45 GiB` worker
    limit profile;
  - `txs_ddf.sort_values('Block_time').persist()` and `dd.merge_asof(...)` can
    still be memory-heavy;
  - `data_operations.py` is ignored/private and local-only.

### Updated baseline observations - 2026-05-05

- Run `145`, bounded smoke `--days 33`, completed successfully:
  - `successful_chunks=11 total_chunks=64`;
  - `features.correlation_data`: `00:11:20`;
  - full run duration: `00:11:27`;
  - profile: `24GB / 2 workers / 2 threads / chunk_size=90`;
  - no spill or worker restart was observed in the log.
- Run `147`, full/live model `model copy 6.json`, was observed live during
  `process_chunk`:
  - scheduler: `tcp://127.0.0.1:60695`;
  - worker profile: `2 workers x 2 threads`, `11.18 GiB` per worker;
  - dashboard workers page showed each worker processing tasks;
  - scheduler task prefixes showed `process_chunk=2392`;
  - observed worker memory was about `0.7-1.3 GiB` per worker, spill `0`;
  - this points to CPU / SQLite / pandas chunk work rather than Dask memory
    pressure.
- Run `148`, full/live with `chunk_size=150`, finished `process_chunk` but
  failed later in the Dask expr graph:
  - `successful_chunks=481 total_chunks=1435`;
  - `features.correlation_data`: `01:22:26`;
  - error: `'MergeAsof' object has no attribute 'how'`;
  - last successful Dask states included `merged_after_asof`,
    `grouped_txs_on_nearest_tmsp`, and `data_for_teach_after_grouped_merge`;
  - decision: keep `dd.merge_asof`, but materialize its output to runtime
    parquet checkpoint before downstream `drop -> groupby -> merge -> compute`.
- Run `150`, live observation during `process_chunk` after the merge-asof
  checkpoint patch:
  - dashboard counts while running:
    `workers=2`, `cores=4`, `idle=0`, `processing=6`, `tasks=1436`,
    `erred=0`;
  - worker memory was still low compared with the 12GB per-worker limit;
  - the workload looked CPU / pandas / SQLite bound rather than memory bound;
  - the active workers used `%TEMP%\dask-scratch-space`, so the configured
    Dask temp directory was not being enforced by config alone.
- Run `150` final result:
  - full/live `main-pipeline` completed successfully;
  - `successful_chunks=481 total_chunks=1435`;
  - `merged_after_asof_checkpoint_read_parquet` was reached;
  - `features.correlation_data`: `01:20:09`;
  - total run duration: `01:21:02`;
  - Dask shutdown emitted a distributed warning about removing a worker and
    recomputing `read_parquet-*` tasks, but the app log shows this happened
    after `Closing dask client` / `Все задачи завершены`; training,
    profit-test, artifact save, and `run_finished status=success` followed.
- Next run profile decision:
  - use `24GB / 4 workers / 2 threads` by default;
  - pass `settings.runtime.DASK_TEMP_DIR` directly to `LocalCluster` as
    `local_directory`;
  - keep `chunk_size=150` unchanged, so the next trial changes only the worker
    shape and temp-dir enforcement.

## Scope

- Affected modules:
  - `modules/dask_client_init/get_dask_client.py`;
  - `modules/teach_and_update_models/orchestrator.py`;
  - `modules/teach_and_update_models/data_operations.py`.
- Affected tables/indexes:
  - read-only access to `data_table`;
  - no index creation, deletion, rebuild, or SQLite mutation in this experiment.
- Affected CLI flags/settings:
  - `main-pipeline` command;
  - Dask local cluster profile;
  - main teaching wallet `chunk_size`;
  - `settings.main_pipeline.MAIN_PIPELINE_CORRELATION_CHUNK_SIZE`.
- Tests/checks:
  - `python -m pytest tests\unit_smoke -q`;
  - inspect run log markers:
    `DASK_CLIENT_PROFILE`, `DASK_CLUSTER_SNAPSHOT`,
    `DASK_DATAFRAME_STATE`, `_TRACKER_INFO stage_finished`.

## Candidate Approaches

### Option A: Increase wallet chunk size only

- Change:
  - keep `24GB / 2 workers / 2 threads`;
  - test `chunk_size=120`, then `150`, then `180` only if prior tier is stable.
- Expected benefit:
  - fewer SQL chunk tasks and fewer Parquet files;
  - moderate speedup while preserving lower concurrency.
- Risks:
  - larger pandas DataFrames per task;
  - possible unmanaged-memory warnings if chunks become too large.
- Expensive operations:
  - full/live pipeline reads from SQLite and writes temporary Parquet chunks.
- Resume/rollback:
  - rollback by returning to the last stable `chunk_size`;
  - temp parquet dirs are cleared before each new chunk generation.
- Verification:
  - full run completes;
  - no worker restart / killed worker / unmanaged-memory warning near limit;
  - `features.correlation_data` duration improves or remains acceptable.

### Option B: Increase thread concurrency

- Change:
  - keep `chunk_size=90` or `120`;
  - test `threads_per_worker=3`.
- Expected benefit:
  - more simultaneous tasks.
- Risks:
  - pandas and SQLite work may increase unmanaged memory faster than Dask can
    spill managed data;
  - harder to diagnose if instability returns.
- Expensive operations:
  - full/live pipeline with higher concurrency.
- Resume/rollback:
  - rollback to `threads_per_worker=2`.
- Verification:
  - compare runtime and memory warnings against Option A.

### Option C: Increase workers

- Change:
  - `n_workers=3`, likely with lower per-worker memory.
- Expected benefit:
  - more process isolation and possible parallelism.
- Risks:
  - more SQLite concurrent reads;
  - smaller memory budget per worker unless total memory increases further;
  - more scheduler overhead.
- Expensive operations:
  - full/live pipeline with higher concurrency.
- Resume/rollback:
  - rollback to `2 workers`.
- Verification:
  - only after Option A/B data suggests CPU/concurrency is the bottleneck.

### Option D: Architecture refactor

- Change:
  - redesign data collection around Dask-friendly partitioning or SQL-side
    filtering rather than pandas chunk extraction plus temp Parquet plus global
    sort/persist.
- Expected benefit:
  - best long-term speed and memory behavior.
- Risks:
  - changes execution shape and may affect feature correctness;
  - requires separate design review and behavior-equivalence checks.
- Expensive operations:
  - likely new full/live validation runs.
- Resume/rollback:
  - keep behind separate branch/experiment until chosen.
- Verification:
  - compare intermediate artifacts, feature schema, action distribution, and
    profit-test output against the corrected current pipeline.

## Data Scale Tiers

- Tiny:
  - unit/smoke tests only; no full Dask/SQLite runtime claim.
- Medium:
  - future controlled `TEACHING_TEST` or sample-mode run, if added/exposed.
- Full/live:
  - current `python main.py main-pipeline` with full model JSON.

## Go / No-Go Criteria

- Correctness:
  - no Python traceback;
  - pipeline reaches model training/evaluation or completes;
  - `PIPELINE_DATA_SUMMARY`, `MODEL_CONTRACT`, and `MODEL_PREDICTION_SUMMARY`
    are present when relevant.
- Runtime:
  - `features.correlation_data` duration improves versus the last stable tier,
    or the added speed risk is rejected.
- Maintainability:
  - only one load parameter changes per trial;
  - trial settings are recorded with run id.
- Recovery:
  - no SQLite mutation;
  - return to last stable profile if worker restarts, memory warnings near
    worker limit, or repeated recomputation appear.

## Behavior vs Performance Separation

- Behavior-equivalence check:
  - do not change feature formulas, labels, timestamp windows, or model params
    during load tuning.
- Performance measurement:
  - measure stage durations, worker warnings, worker memory snapshots, and Dask
    DataFrame metadata.

## Rollback / Recovery Plan

- Last known cautious profile:
  - `total_memory='24GB'`;
  - `n_workers=2`;
  - `threads_per_worker=2`;
  - `chunk_size=90`.
- To rollback:
  - restore `chunk_size=90`;
  - keep the same Dask client profile unless the issue points to memory limit;
  - rerun unit smoke before the next full trial.

## Measurements

| Option | Scale | Command | Runtime | Correctness | Notes |
| --- | --- | --- | --- | --- | --- |
| Baseline cautious | Full/live | `python main.py main-pipeline` | run `107` in progress | unknown | `24GB / 2x2 / chunk=90`; dashboard showed low managed memory during `process_chunk` |
| Bounded smoke | 33 days | `scripts\run_main_pipeline_smoke.py --days 33` | run `145`: `00:11:27`; `features.correlation_data`: `00:11:20` | success | `successful_chunks=11 total_chunks=64`; `24GB / 2x2 / chunk=90`; no spill/restart observed |
| Current full/live observation | Full/live | `python main.py main-pipeline` | run `147`: interrupted after `00:12:49`; `features.correlation_data`: `00:12:43` | interrupted | live dashboard: `2 workers x 2 threads`, `process_chunk=2392`, memory about `0.7-1.3 GiB` per worker, spill `0` |
| A1 chunk 120 | Full/live | `python main.py main-pipeline` | pending | pending | paused until one successful full pipeline run |
| A2 chunk 150 | Full/live | `python main.py main-pipeline` | run `148`: `features.correlation_data` failed after `01:22:26` | failed | chunking completed with `successful_chunks=481 total_chunks=1435`; downstream Dask expr failed on `MergeAsof.how`; added merge-asof parquet checkpoint before retry |
| Merge-asof checkpoint | Full/live | `python main.py main-pipeline` | run `150`: total `01:21:02`; `features.correlation_data` `01:20:09` | success | `successful_chunks=481 total_chunks=1435`; checkpoint marker reached; shutdown warning was cleanup noise |
| C1 worker shape 4x2 | Full/live | `python main.py main-pipeline` | pending | pending | next-run default: `24GB / 4 workers / 2 threads`, explicit `LocalCluster(local_directory=DASK_TEMP_DIR)`, `chunk_size=150` unchanged |
| B1 threads 3 | Full/live | `python main.py main-pipeline` | pending | pending | only after chunk tuning data |

## Cleanup Gate

- [ ] Chosen code moved to production path.
- [ ] Obsolete `experimental*` files removed or documented.
- [ ] Obsolete `experimental_` tables removed or documented.
- [ ] Production path checked for accidental experimental dependencies.
- [ ] Tests/docs updated.

## Decision Record

- Chosen option: pending.
- Rejected options: pending.
- Tradeoffs accepted:
  - tune load slowly to preserve correctness and diagnosability.
- Validation performed:
  - run `145` bounded smoke completed successfully under the cautious profile.
  - run `148` full/live failed after chunk generation on Dask expr
    `MergeAsof.how`, so load tuning is blocked by compatibility until the
    checkpoint approach is validated.
- Remaining debt:
  - Dask architecture refactor may still be needed after correctness is proven.
- Follow-up:
  - rerun with `chunk_size=150` and merge-asof checkpoint enabled;
  - check for `merged_after_asof_checkpoint_read_parquet` in the new log;
  - do not increase `threads_per_worker` or `n_workers` before collecting
    a successful checkpoint run, because the live observation shows low memory
    pressure but many Python/pandas-heavy `process_chunk` tasks.
