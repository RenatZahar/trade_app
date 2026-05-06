# Dependency upgrade audit - 2026-05-04

Status: applied to project `.venv` after isolated latest-stack verification.

## Goal

Review how far the project dependencies lag behind current PyPI releases and
plan a safe upgrade path that may improve main pipeline stability and speed
without silently changing model/data behavior.

## Hypothesis

Updating Dask, pandas, pyarrow, numpy, scipy, scikit-learn, and related runtime
packages may improve Dask dataframe execution, parquet I/O, scheduler behavior,
and ML runtime performance.

The likely speed gain is not guaranteed. Current `main-pipeline` bottlenecks may
also be algorithmic: many parquet chunks, `merge_asof`, shuffle/groupby shape,
SQLite access pattern, and wallet-level collection strategy.

## Current Baseline

Environment:

- project venv: Python `3.12.2`;
- active branch: `feature/iteration-14-main-pipeline-correctness`;
- command used for audit:
  - `.venv\Scripts\python.exe -m pip list --outdated --format=json`;
  - `.venv\Scripts\python.exe -m pip install --dry-run --upgrade ...`;
  - static import scan over project `.py` files excluding virtualenvs.

Validation before this audit:

- `.venv\Scripts\python.exe -m pip check` passed;
- `.venv\Scripts\python.exe -m pytest tests\unit_smoke -q`:
  - `85 passed, 1 warning`;
- Dask dataframe backend intentionally uses classic Dask:
  - `dataframe.query-planning=False`;
  - `dask.dataframe.core.DataFrame`;
- `dask-expr` is not installed and is not listed in `requirements.lock.txt`.

## Current vs Latest Key Packages

Latest versions were collected from PyPI via `pip list --outdated` on
2026-05-04.

| Package | Current | Latest | Main risk area |
| --- | ---: | ---: | --- |
| dask | 2024.5.2 | 2026.3.0 | Dask dataframe/shuffle/scheduler behavior |
| distributed | 2024.5.2 | 2026.3.0 | Worker lifecycle, dashboard, scheduler |
| pandas | 2.2.1 | 3.0.2 | API behavior, dtype changes, groupby/resample semantics |
| pyarrow | 16.0.0 | 24.0.0 | parquet I/O, dtype roundtrip |
| numpy | 1.26.4 | 2.4.4 | binary compatibility, numeric behavior |
| scipy | 1.13.0 | 1.17.1 | peak detection / scientific stack |
| scikit-learn | 1.5.0 | 1.8.0 | model defaults, metrics, serialization behavior |
| numba | 0.60.0 | 0.65.1 | numpy compatibility |
| fastparquet | 2024.2.0 | 2026.3.0 | parquet fallback behavior |
| Flask | 3.0.3 | 3.1.3 | local app runtime |
| requests | 2.31.0 | 2.33.1 | price/API calls |
| aiohttp | 3.9.5 | 3.13.5 | parser async RPC/client behavior |
| aiosqlite | 0.20.0 | 0.22.1 | async parser DB access |
| redis | 5.2.0 | 7.4.0 | parser/runtime integration |
| plotly | 5.21.0 | 6.7.0 | Flask graph rendering |
| matplotlib | 3.9.0 | 3.10.9 | notebooks/debug plots |
| pytest | 9.0.2 | 9.0.3 | tests only |

Summary:

- locked packages: `157`;
- outdated packages reported by pip: `126`;
- Dask lag:
  - current: `2024.5.2`;
  - latest: `2026.3.0`;
  - approximate lag: about 22 months and many release lines.

## Directly Imported External Packages

Static import scan found these external packages in project code/tests:

- core data/runtime:
  - `pandas`;
  - `numpy`;
  - `dask`;
  - `distributed`;
  - `sklearn`;
  - `scipy`;
  - `joblib`;
- DB/parser/runtime:
  - `aiohttp`;
  - `aiosqlite`;
  - `bitcoinrpc` / `python-bitcoinrpc`;
  - `requests`;
  - `redis`;
  - `dotenv`;
  - `psutil`;
- web/visualization:
  - `flask`;
  - `plotly`;
- tests/dev:
  - `pytest`.

Many packages in `requirements.lock.txt` are transitive dependencies or notebook
tooling, especially Jupyter-related packages. They should not drive the upgrade
strategy unless they block installation or tests.

## Dry-Run Findings

### Dask-only upgrade

Command:

```powershell
.venv\Scripts\python.exe -m pip install --dry-run --upgrade `
  "dask==2026.3.0" "distributed==2026.3.0"
```

Result:

- resolver would install only:
  - `dask-2026.3.0`;
  - `distributed-2026.3.0`;
- current `pandas==2.2.1` and `pyarrow==16.0.0` remain acceptable for this
  dry-run.

Interpretation:

- Dask can be tested as a narrow upgrade first;
- this is lower risk than upgrading all scientific packages at once.

### Full scientific core upgrade

Command:

```powershell
.venv\Scripts\python.exe -m pip install --dry-run --upgrade `
  "dask==2026.3.0" `
  "distributed==2026.3.0" `
  "pandas==3.0.2" `
  "pyarrow==24.0.0" `
  "numpy==2.4.4" `
  "scipy==1.17.1" `
  "scikit-learn==1.8.0" `
  "numba==0.65.1"
```

Result:

- resolver found a compatible candidate set:
  - `dask-2026.3.0`;
  - `distributed-2026.3.0`;
  - `pandas-3.0.2`;
  - `pyarrow-24.0.0`;
  - `numpy-2.4.4`;
  - `scipy-1.17.1`;
  - `scikit-learn-1.8.0`;
  - `numba-0.65.1`;
  - `llvmlite-0.47.0`.

Interpretation:

- a latest scientific stack is installable in principle;
- it is not safe to apply directly to the current production `.venv` without
  a separate test environment and behavior checks.

## Candidate Approaches

### Option A - Dask-only upgrade first

What changes:

- upgrade only `dask` and `distributed` to `2026.3.0`;
- keep pandas/pyarrow/numpy/sklearn/scipy unchanged.

Pros:

- isolates scheduler/dataframe runtime changes;
- lowest blast radius;
- directly targets the latest Dask gap.

Cons:

- may not unlock parquet/pandas/pyarrow performance improvements;
- may still hit dataframe backend changes in newer Dask.

### Option B - Scientific core upgrade

What changes:

- upgrade Dask/distributed + pandas + pyarrow + numpy + scipy + scikit-learn +
  numba.

Pros:

- best chance of broad performance improvements;
- removes old compatibility layers;
- closer to current ecosystem.

Cons:

- highest risk of behavior changes;
- pandas 3 and numpy 2 can surface many API/dtype issues;
- sklearn model results and serialization may change;
- harder to isolate the cause of regressions.

### Option C - Dependency cleanup before upgrade

What changes:

- split dependencies into runtime, dev/test, notebook/optional groups;
- remove packages not directly required for `main-pipeline`.

Pros:

- smaller upgrade surface;
- easier future maintenance.

Cons:

- takes longer;
- can accidentally remove notebook/dev tools the project still uses informally.

## Recommended Plan

Do not upgrade the current `.venv` in place first.

Recommended sequence:

1. Keep current `.venv` as baseline.
2. Create a separate experimental environment:
   - `.venv_upgrade_dask`;
   - or `.venv_upgrade_latest`.
3. Phase 1: Dask-only upgrade:
   - install `dask==2026.3.0`, `distributed==2026.3.0`;
   - keep classic dataframe setting if still supported;
   - run `pip check`;
   - run `python -m pytest tests\unit_smoke -q`;
   - run a tiny Dask dataframe/parquet/merge_asof smoke.
4. If Phase 1 passes, run one controlled `main-pipeline` attempt or a smaller
   equivalent stage if available.
5. Phase 2: full scientific core upgrade in a separate environment.
6. Compare behavior and runtime against baseline before changing
   `requirements.lock.txt`.

## Scale Tiers

- `tiny`:
  - import checks;
  - unit smoke tests;
  - synthetic Dask dataframe/parquet/merge/groupby smoke.
- `medium`:
  - controlled subset of feature pipeline if available;
  - no broad SQLite mutation.
- `full/live`:
  - `python main.py main-pipeline`;
  - only after `tiny` and `medium` pass.

## Go / No-Go Criteria

Go:

- `pip check` passes;
- `tests\unit_smoke` passes;
- Dask dataframe backend behavior is understood and logged;
- no `dask-expr` reintroduction unless explicitly chosen;
- tiny Dask dataframe smoke passes;
- main pipeline reaches farther than run `107` without a new compatibility
  error.

No-go:

- dependency resolver introduces incompatible numpy/scipy/numba/sklearn combo;
- Dask classic dataframe backend is removed or incompatible and requires a
  production code change;
- unit smoke failures are caused by real API changes;
- model/profit-test output changes without an explanation.

## Rollback / Recovery

- Current `.venv` can be kept unchanged as baseline.
- Old project venv backup exists locally:
  - `.venv_py311_backup_20260504_203027`;
- Git restore point for iteration 14 exists separately.
- Do not overwrite `requirements.lock.txt` with latest stack until checks pass.

## Cleanup Gate

Before closing the experiment:

- remove failed experimental venvs;
- keep only the chosen lock changes;
- document chosen stack in iteration docs;
- record whether speed improved, stayed the same, or regressed.

## Execution - 2026-05-04

### Tests added before applying the upgrade

Before replacing the project `.venv`, added focused smoke contracts for the
dependency-sensitive parts of the pipeline:

- core package imports for Dask, pandas, numpy, pyarrow, scipy and sklearn;
- Dask dataframe backend compatibility:
  - Dask `2024.x` can still use classic dataframe;
  - Dask `2026.x` requires query-planning / expr dataframe;
- synthetic Dask parquet, `merge_asof`, groupby and compute path;
- pandas `resample(..., "10min")` and groupby-apply behavior;
- sklearn `Pipeline(StandardScaler(), ElasticNet())` behavior.

Reason:

- the project cannot safely update Dask/Pandas/Sklearn first and only then
  discover that basic dataframe/model contracts no longer import.

### Isolated latest-stack environment

Created separate environment:

```powershell
.venv_upgrade_latest
```

Key package versions verified there:

- Python: `3.12.2`;
- Dask: `2026.3.0`;
- distributed: `2026.3.0`;
- pandas: `3.0.2`;
- pyarrow: `24.0.0`;
- numpy: `2.4.4`;
- scipy: `1.17.1`;
- scikit-learn: `1.8.0`;
- numba: `0.65.1`;
- fastparquet: `2026.3.0`;
- Flask: `3.1.3`;
- requests: `2.33.1`.

Findings:

- Dask `2026.3.0` no longer supports the legacy/classic dataframe
  implementation. Setting `dataframe.query-planning=False` raises:
  - `NotImplementedError: The legacy implementation is no longer supported`.
- The project Dask setting was changed from a hard classic backend contract to a
  version-aware setting:
  - Dask before `2025`: `dataframe.query-planning=False`;
  - Dask `2025+`: `dataframe.query-planning=True`.
- This means `dask-expr` is no longer optional for latest Dask behavior; it is
  the current Dask dataframe implementation path.

Validation in `.venv_upgrade_latest`:

```powershell
.venv_upgrade_latest\Scripts\python.exe -m pip check
# No broken requirements found.

.venv_upgrade_latest\Scripts\python.exe -m pytest tests\unit_smoke -q
# 90 passed, 2 warnings
```

### Fresh lock install conflict

The first regenerated latest lock installed in the already-upgraded environment
but failed from a fresh `.venv` because:

- `nbconvert==7.17.1` depends on `bleach[css]`;
- `bleach[css]==6.3.0` requires `tinycss2<1.5`;
- the resolver had selected `tinycss2==1.5.1`.

Resolution:

- pin `tinycss2==1.4.0`;
- regenerate `requirements.lock.txt`;
- verify a fresh project `.venv` can install from the lock.

This is the only intentionally non-latest package after the upgrade:

```powershell
.venv\Scripts\python.exe -m pip list --outdated --format=json
# tinycss2 1.4.0 -> 1.5.1, intentionally held for bleach[css]
```

### Project `.venv` replacement

Previous Python `3.12` project environment was preserved locally:

```text
.venv_py312_pre_latest_backup_20260504_220339
```

Then the project `.venv` was recreated and installed from
`requirements.lock.txt`.

Validation in the new project `.venv`:

```powershell
.venv\Scripts\python.exe --version
# Python 3.12.2

.venv\Scripts\python.exe -m pip check
# No broken requirements found.

.venv\Scripts\python.exe -m pytest tests\unit_smoke -q
# 90 passed, 2 warnings
```

Warnings:

- `distributed.diagnostics.nvml` warns that `pynvml` is deprecated even though
  `nvidia-ml-py` is installed. This is a dependency/runtime warning, not a
  smoke-test failure.
- The synthetic ElasticNet test still has a known sklearn
  `UndefinedMetricWarning` because the tiny fixture has labels with no predicted
  samples.

## Current Decision

The latest dependency stack is now applied to the project `.venv` and recorded
in `requirements.lock.txt`.

Accepted tradeoffs:

- Dask latest requires the current query-planning dataframe path. The project no
  longer forces classic dataframe on Dask `2026.x`.
- `tinycss2` stays on `1.4.0` to keep fresh installs compatible with
  `nbconvert -> bleach[css]`.
- Unit/smoke tests pass, but a full `main-pipeline` run is still required before
  treating the updated runtime as operationally proven.

Next recommended action:

- run the short compatibility smoke first:
  - `.venv\Scripts\python.exe scripts\run_main_pipeline_smoke.py --days 7`;
- then run one full `python main.py main-pipeline` from the updated `.venv`
  when the machine is not under unrelated heavy load;
- compare failure/success point and Dask logs against runs `107`, `109`, and
  `110`;
- only after one successful run, resume Dask load tuning.

## Post-Upgrade Runtime Notes

Run `109` reached the second Dask stage and failed with a pandas 3 compatibility
issue:

- `ValueError: assignment destination is read-only`;
- failing function: `import_peak_intervals`;
- fix: write interval markers into explicit writable NumPy copies.

Run `110` was started after the fix but stopped manually while the machine was
under unrelated gaming load. It should not be used for performance conclusions.

Scenario validation remains open after the dependency upgrade:

- full `main-pipeline`;
- small `param-grid`;
- explicit-block `test downloaded-from-btc-data`;
- parser monitor startup as a separate controlled check.
