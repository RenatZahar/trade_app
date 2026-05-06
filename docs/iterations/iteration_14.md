# Iteration 14 - Main ML pipeline correctness

## Тема

Исправление небольших, но критичных вопросов корректности в основном ML
pipeline перед доверием к model/profit-test результатам.

## Статус

Started

## Restore point

Перед любыми изменениями main pipeline зафиксирована точка восстановления:

- commit: `cad3a11 Start main pipeline correctness iteration`;
- tag: `restore/iteration-14-start`;
- branch: `feature/iteration-14-main-pipeline-correctness`;
- tag pushed to origin: yes.

Если после будущих правок появится непонятный regression или сомнение в
логике, сравнивать поведение нужно относительно этого commit/tag, а не
относительно промежуточных WIP-состояний.

## Дата старта

2026-05-04

## Work Status

Use `$iteration-handoff` when continuing this iteration in a new chat. The next
agent should read this section first and continue the item marked
`in_progress`, unless the user names another item.

### WS-14-001 - Dask merge_asof compatibility

Status: done

Goal:

- Get at least one successful `main-pipeline` or short smoke run after the
  Dask/distributed `2026.3.0` dependency upgrade.
- Keep `dd.merge_asof` if possible instead of immediately replacing it with a
  manual `searchsorted` implementation.

Current context:

- Latest useful full run: `141`.
- Run `141` completed correlation chunk processing:
  - `successful_chunks=237 total_chunks=237`;
  - then failed in `features.correlation_data`;
  - error: `'MergeAsof' object has no attribute 'how'`.
- Run `142` failed before `merge_asof` because `process_chunk` referenced
  local caller variables `txs_dir` / `cor_dir` inside a Dask task.
- Run `143` reached the `merge_asof` graph, but parquet metadata showed
  `txs_of_chunk_with_intervals` had `0` rows while correlation parquet had
  rows with fake `Wallet_id='0.0'`; the Dask error was
  `IndexError: list index out of range`.
- Run `144` after the fake-wallet fix failed fast with
  `successful_chunks=0 total_chunks=11`; the 7-day smoke window is too short
  for the current `correlation_threshold=0.2` and does not validate
  `merge_asof`.
- Run `145` bounded smoke `--days 33` completed successfully:
  `successful_chunks=11 total_chunks=64`.
- Run `148` full/live with `chunk_size=150` reached the same Dask expr failure:
  `successful_chunks=481 total_chunks=1435`, then
  `'MergeAsof' object has no attribute 'how'`.
- Run `150` full/live with the merge-asof parquet checkpoint completed
  successfully:
  - model source:
    `data/models/new_models/model copy 6.json`;
  - source params:
    `ElasticNet(alpha=2.15443469, l1_ratio=0)`,
    `decision_threshold=0.15`, `correlation_type=basic`,
    `correlation_threshold=0.2`, `txs_count_of_wallets=5`,
    `iterations=1`, `training_data_duration_months=12`,
    `profit_test_months=2`, `model_relevance_period_months=2`,
    `time_to_get_cmlt_day=14`;
  - `successful_chunks=481 total_chunks=1435`;
  - `features.correlation_data`: `01:20:09`;
  - `run_finished status=success`: `01:21:02`;
  - checkpoint marker reached:
    `merged_after_asof_checkpoint_read_parquet`.
- Run `150` saved temp parquet artifacts:
  - `txs_of_chunk_with_intervals`: `481` files, `59,410` rows,
    `625` unique wallets;
  - `correlation_wallets_df`: `481` files, `625` rows / wallets;
  - `3_merged_after_asof_checkpoint`: `481` files, `59,410` rows,
    `625` unique wallets.
- Run `150` data windows:
  - `teaching_start_tmsp=1701991824`;
  - `teaching_end_tmsp=1733095824`;
  - `profit_test_start_tmsp=1733095825`;
  - `profit_test_end_tmsp=1738279825`;
  - SQLite `data_table` max observed block time/height:
    `1738279826` / `881562`, so there is data immediately after
    `profit_test_end_tmsp`; this run was not blocked by a stale DB end.
- Run `150` model/profit behavior is suspicious but outside this Dask
  compatibility item:
  - profit-test rows: `8,640`;
  - actual labels: `0=8558`, `-1=67`, `1=15`;
  - predicted actions: `0=8638`, `-1=2`, `1=0`;
  - no buy signal was produced, so no trade was opened and `profit=1000.0`
    means zero return, not a profitable model.
- The distributed warning about removing a worker and recomputing
  `read_parquet-*` tasks appeared during intentional Dask client shutdown after
  `Closing dask client` / `Все задачи завершены`; the pipeline continued to
  train/evaluate/save and finished successfully, so this is cleanup noise for
  run `150`, not the failure mode.
- A minimal local `dd.merge_asof(..., direction="nearest")` smoke works on
  Dask `2026.3.0`, so the failure is likely tied to this project graph shape:
  `merge_asof -> assign/drop -> groupby.agg -> merge -> compute`.

Current local changes:

- `data_operations.py` is ignored/private and was patched locally.
- `dd.merge_asof` now uses `tolerance` derived from
  `settings.price_peaks.line_time_duration_min`.
- Active window contract:
  - `line_time_duration_min = 10`;
  - price row duration = `600` seconds;
  - asof matching half-window = `300` seconds.
- Added Dask checkpoints:
  - `merged_after_asof`;
  - `merged_after_asof_checkpoint_read_parquet`;
  - `merged_after_drop_before_groupby`;
  - `grouped_txs_on_nearest_tmsp`;
  - `data_for_teach_after_grouped_merge`.
- `process_chunk` now receives `txs_dir` and `cor_dir` explicitly.
- `calculate_correlation_basic` now drops below-threshold rows with missing
  `Wallet_id` before `fillna(0.0)`, so fake wallet id `0.0` is not propagated.
- `process_chunk` normalizes `Wallet_id` type before filtering and returns
  `False` instead of writing empty tx parquet chunks.
- `process_chunk` now returns per-chunk wallet filter stats, and
  `get_corelation_of_wallets_df_with_dask(...)` logs
  `CORRELATION_WALLET_FILTER_SUMMARY` with counts before/after tx lookup,
  time/amount filtering, interval import, and `correlation_threshold`.
- `teach_n_test_data_with_basic_corrs(...)` now materializes the
  `dd.merge_asof(...)` output to runtime parquet directory
  `3_merged_after_asof_checkpoint` and reads it back before downstream
  `drop -> groupby -> merge -> compute`.

Verification:

- `.venv\Scripts\python.exe -m pytest tests\unit_smoke\test_correlation_pipeline_contracts.py tests\unit_smoke\test_dependency_runtime_contracts.py -q`
- Result after latest local fixes: `21 passed`.

Next step:

- Continue Dask load tuning from the documented ladder.
- Next full run should use the staged `24GB / 4 workers / 2 threads` profile
  and keep `chunk_size=150`.
- Keep the merge-asof parquet checkpoint in place unless a later decision
  replaces this join path.

Do not touch without confirmation:

- SQLite maintenance, indexes, or bulk data mutations.
- Parser runtime behavior.
- Collector/wallet_stats redesign from iteration 15 before this item gets a
  successful run or a stable failure diagnosis.

Status notes:

- 2026-05-05: `iteration-handoff` skill created.
- 2026-05-05: cost-control rules moved into `AGENTS.md` and
  `docs/codex_cost_control.md`.
- 2026-05-05: Dask `merge_asof` tolerance/logging patch added locally.
- 2026-05-05: Runs `142-144` diagnosed. Fixed Dask task path scoping and fake
  `Wallet_id='0.0'` propagation. The 7-day smoke now fails fast with no
  successful correlation chunks, so the next validation needs a wider bounded
  smoke or a full run.
- 2026-05-06: Run `148` confirmed the full-scale Dask expr `MergeAsof.how`
  failure. Added runtime parquet checkpoint immediately after `dd.merge_asof`.
- 2026-05-06: Run `150` completed full `main-pipeline` successfully with the
  merge-asof parquet checkpoint. Compatibility item is done; performance/load
  tuning remains.
- 2026-05-06: Profit artifact from run `150` was reviewed. It confirms the
  pipeline can complete, but the selected JSON/model produced no buy signals;
  model quality and stage contracts should be handled as a separate follow-up.
- 2026-05-06: Added `CORRELATION_WALLET_FILTER_SUMMARY` log marker for future
  runs to explain how many wallets survive each correlation-data filter.

### WS-14-002 - Cost-control and new-chat workflow

Status: done

Result:

- Added project cost-control rules to `AGENTS.md`.
- Created `docs/codex_cost_control.md`.
- Created `$iteration-handoff` skill under `.agents/skills/iteration-handoff`.
- Iteration docs now use `## Work Status` as the primary resume point for new
  chats.

### WS-14-003 - Refactor entry logic trace

Status: done

Result:

- Added `Refactor Entry Check` to `AGENTS.md`.
- Rule: before substantial existing-code refactors, first write a logic trace:
  caller responsibility, callee responsibility, duplicated responsibility,
  dead/unclear code, observable contract, narrow verification.
- This rule does not apply to clearly new code, smoke tests, technical docs,
  log wording, argparse text, or small pure-function tests.

## Контекст

Итерация 13 закрыла parser backfill stability как `Done with follow-ups`.
Следующий текущий приоритет из `docs/active_work_plan.md` - исправить main ML
pipeline correctness.

Фокус 14-й итерации - не новая модель и не оптимизация качества сигнала, а
контракты данных между train/predict/profit-test:

- train/predict preprocessing mismatch;
- случайное попадание `index` в признаки;
- timestamp filter parentheses и выравнивание данных;
- drift между `threshold` и `decision_threshold`;
- feature schema contract для train и predict.

## Цель итерации

Сделать основной ML pipeline достаточно корректным, чтобы последующие
profit-test и model comparison результаты можно было трактовать как инженерный
сигнал, а не как артефакт несовпадающих preprocessing/feature contracts.

## Что входит в scope

### 1. Train/predict preprocessing contract

- Проверить, где train делает `StandardScaler().fit_transform(...)`.
- Проверить, где predict/profit-test вызывает модель на raw features.
- Выбрать минимальный безопасный контракт:
  - `sklearn Pipeline(StandardScaler(), ElasticNet())`;
  - либо явное сохранение и применение scaler рядом с моделью.
- Добавить focused test или smoke-проверку на одинаковый preprocessing path.

### 2. Feature schema contract

- Явно зафиксировать список model feature columns.
- Исключить случайный технический `index`, если он не является осознанным
  признаком.
- Определить поведение при missing/extra columns:
  fail-fast для train/predict mismatch вместо молчаливого переупорядочивания.

### 3. Timestamp filters and data alignment

- Найти фильтры вида `Timestamp >= start & Timestamp <= end`.
- Исправить приоритет операций через явные parentheses:
  `(Timestamp >= start) & (Timestamp <= end)`.
- Проверить, не создает ли alignment скрытый overlap train/test windows или
  label leakage.

### 4. Threshold config cleanup

- Найти места, где одновременно используются `threshold` и
  `decision_threshold`.
- Свести их к одному читаемому контракту или добавить адаптер с явной
  совместимостью, если старое имя еще нужно.

## Out of scope

- Подбор новых model families.
- Profit-test метрики, комиссии, slippage и walk-forward baseline.
- Bulk SQLite maintenance, индексы, миграции или физический перенос данных.
- Parser runtime changes.
- Сравнение current pipeline с legacy notebook flow.

## Риски

- Маленькая правка preprocessing может изменить все model/profit-test числа;
  это ожидаемо, но должно быть явно зафиксировано.
- Feature schema fail-fast может вскрыть старые неявные зависимости в
  profit-test.
- Timestamp fix может изменить выборку данных; нужно проверять результат узкими
  тестами, а не считать это косметикой.
- Если задача неожиданно затронет SQLite bulk work, нужно остановиться и
  перейти к data safety design review.

## Варианты вмешательства

### Minimal patch

- Исправить только подтвержденные локальные баги:
  preprocessing mismatch, `index`, timestamp parentheses, threshold drift.
- Добавить узкие unit/smoke tests вокруг измененных контрактов.
- Плюсы: быстро, низкий blast radius.
- Минусы: архитектура pipeline может остаться неидеальной.

### Medium refactor

- Вынести feature schema/preprocessing в отдельный локальный слой контракта.
- Train и predict используют один helper для column selection/order.
- Плюсы: меньше повторения и скрытых mismatch.
- Минусы: выше риск задеть старый runtime.

### Rewrite slice

- Пересобрать train/predict/profit-test вокруг единого artifact contract:
  model pipeline, schema, metadata, thresholds.
- Плюсы: правильнее долгосрочно.
- Минусы: слишком большой scope для итерации "небольших вопросов"; вероятно
  потребует отдельной архитектурной итерации.

## Выбранный план

Стартовая рекомендация: начать с `Minimal patch`, но держать границу так, чтобы
не смешивать исправление correctness с redesign всего ML pipeline.

### Safety rules for this iteration

1. Не менять одновременно feature generation, model fitting и profit-test
   execution в одном коммите.
2. Перед каждой кодовой фазой сначала фиксировать диагноз: текущий контракт,
   чем он опасен, ожидаемое новое поведение.
3. Каждая правка должна иметь narrow verification: unit/smoke test или
   минимальный воспроизводимый сценарий.
4. Не удалять debug artifacts/legacy branches кода в рамках correctness patch,
   если они не мешают контракту напрямую.
5. Не запускать bulk SQLite maintenance, индексы, migrations или полные
   пересчеты данных без отдельного data safety design review.
6. После каждой фазы проверять `git diff` и держать коммиты маленькими, чтобы
   rollback был дешевым.

### Файлы-кандидаты

- `modules/teach_and_update_models/model_classes.py`:
  - `ElasticNetModel.train_model_specific(...)` сейчас делает
    `StandardScaler().fit_transform(...)` перед fit;
  - `GeneralModel.calculate_total_value(...)` вызывает `model.predict(...)` на
    `data_copy`, который не проходит тот же scaler;
  - threshold naming расходится между `threshold` и `decision_threshold`;
  - в коде уже есть warning о недостающей feature-schema проверке.
- `modules/teach_and_update_models/data_operations.py`:
  - timestamp filters в двух местах используют опасную форму
    `data_for_teach_df['Timestamp'] >= teaching_start_tmsp & (...)`;
  - `merge_asof(..., direction='nearest')` требует отдельного решения:
    исправлять сейчас только если есть явный correctness-баг, иначе
    документировать как follow-up.
- `modules/teach_and_update_models/orchestrator.py`:
  - связывает feature preparation, train, profit-test и save stages;
  - должен остаться тонким orchestration слоем, без новой ML-логики.
- `tests/unit_smoke/`:
  - место для focused tests на feature schema, scaler contract, timestamp
    filters и threshold normalization.

### Phase 0 - Baseline and diagnostics only

Что:

- Зафиксировать текущий control flow train -> predict -> profit-test по
  конкретным строкам кода.
- Найти все места, где создаются/очищаются feature columns.
- Найти все direct writes debug parquet вроде `data_copy_for_predictions.parquet`
  и решить, трогать ли их в этой итерации.

Почему:

- Нельзя исправлять scaler или schema вслепую: main risk здесь не crash, а
  тихое изменение смысла признаков.

Ожидаемый результат:

- Короткий diagnosis в iteration doc или отдельном сообщении перед первым
  code patch.
- Решение: какие пункты точно правим, какие оставляем follow-up.

### Phase 0 diagnosis - 2026-05-04

Статус: completed as docs-only diagnostics. Pipeline-код не менялся.

#### Current train -> predict -> profit-test flow

1. CLI entrypoint:
   - `main.py:25-29` обрабатывает команду `main-pipeline`;
   - вызывает `runtime_scenarios.prepare_training_data_and_train_new_model()`;
   - runtime logging стартует до сценария через `start_runtime_logging(args)`.
2. Scenario layer:
   - `runtime_scenarios.py:40-49` делает preflight, warning по индексам,
     стартует Flask, обновляет BTC price data, обновляет peaks и вызывает
     `train_new_model_from_json(TEACHING_TEST=0)`;
   - это значит, что реальный `main-pipeline` перед ML-частью имеет внешние
     side effects. В рамках первых correctness patches не трогаем эти шаги.
3. Model config loading:
   - `training_entrypoints.py:29-41` форматирует JSON в `data/models/new_models`,
     берет первый не-example файл через `check_for_new_models()` и передает
     `model_info` в `teach_model(...)`;
   - текущий рабочий файл `data/models/new_models/model copy 5.json` содержит
     `decision_threshold`, а example/param-grid configs содержат `threshold`.
4. Orchestration:
   - `orchestrator.py:26-101` на каждую временную итерацию:
     - строит `model.tmsps_data`;
     - вызывает `do.get_corelation_by_tmsp_df(...)`;
     - применяет `do.clean_data(...)` к train и profit-test DataFrame;
     - вызывает `model.train_model_specific(...)`;
     - отдельно вызывает `model.calculate_total_value(...)`;
     - сохраняет model/profit artifacts.
5. Data preparation:
   - `data_operations.py:127-161` собирает wallets/correlations/features и в
     конце делает `reset_index(inplace=True)` для train и profit-test frames;
   - из-за этого появляется обычная колонка `index`, которая дальше не
     удаляется `clean_data(...)`.
6. Feature cleanup:
   - `data_operations.py:858-890` удаляет service columns вроде `Timestamp`,
     `Block_time`, `Nearest_tmps_from_learning_data`, но не удаляет `index`;
   - значит `index` становится candidate model feature в train и predict.
7. Model fit:
   - `model_classes.py:197-204` создает raw `ElasticNet`, вручную делает
     `StandardScaler().fit_transform(...)`, затем превращает scaled array назад
     в DataFrame;
   - `model_classes.py:259-264` обучает raw `ElasticNet` уже на scaled DataFrame;
   - scaler не сохраняется на `self`, не попадает в saved model artifact и не
     применяется в profit-test predict.
8. Predict/profit-test:
   - `model_classes.py:140-189` берет `self.model`, делает
     `data.drop(columns=['Action', 'Price', 'Predicted_Action'])` и вызывает
     `model.predict(data_copy)`;
   - этот `data_copy` не проходит тот же scaler;
   - feature schema не проверяется, хотя рядом уже есть warning/comment с
     идеей `feature_names_in_`;
   - `data_copy_for_predictions.parquet` и `data_after_predictions.parquet`
     пишутся в текущую директорию модуля, потому что module import делает
     `os.chdir(script_dir)`.

#### Confirmed findings

1. Timestamp filter precedence bug.

   Текущие участки:

   - `data_operations.py:634-637`;
   - `data_operations.py:737-740`.

   Форма:

   ```python
   data_for_teach_df['Timestamp'] >= teaching_start_tmsp &
   (data_for_teach_df['Timestamp'] <= teaching_end_tmsp)
   ```

   Почему это опасно:

   - `&` применяется не как логическое "между двумя условиями", а внутри правой
     части comparison;
   - на минимальном примере ожидаемая маска `[False, True, False]` превращается
     в `[True, True, True]`;
   - это может расширять train window и незаметно менять выборку.

   Диагностический snippet:

   ```python
   correct = (df["Timestamp"] >= start) & (df["Timestamp"] <= end)
   current = df["Timestamp"] >= start & (df["Timestamp"] <= end)
   # correct -> [False, True, False]
   # current -> [True, True, True]
   ```

   Решение: Phase 1 должна исправить только эти filters и добавить focused
   unit test на маленьком DataFrame.

2. Accidental `index` feature leakage.

   Текущие участки:

   - `data_operations.py:158-159` добавляет колонку `index`;
   - `data_operations.py:858-890` не удаляет `index`;
   - `model_classes.py:201-204` обучает модель на всех колонках кроме
     `Action`, `Price`;
   - `model_classes.py:150` predict/profit-test также оставляет `index`.

   Почему это опасно:

   - `index` не является рыночным/поведенческим признаком;
   - он зависит от порядка формирования DataFrame и parquet/load/reset path;
   - модель может получить ложный сигнал, который не переносится между runs.

   Диагностический snippet:

   ```python
   raw.reset_index(inplace=True)
   raw.drop(columns=["Action", "Price"]).columns.tolist()
   # ["index", "Timestamp", "feature"]
   ```

   Решение: Phase 2 должна ввести минимальный feature schema helper и явно
   исключить `index`.

3. Train/predict preprocessing mismatch.

   Текущие участки:

   - `model_classes.py:200-204` fit path делает `StandardScaler().fit_transform`;
   - `model_classes.py:264` fit raw `ElasticNet` на scaled `X_train`;
   - `model_classes.py:154` predict path вызывает raw `model.predict(data_copy)`.

   Почему это опасно:

   - model coefficients обучены на standardized scale;
   - profit-test подает raw scale;
   - результат может быть численно валидным, но логически неправильным;
   - saved artifact через `save_model()` сохраняет только raw model, не scaler.

   Решение: Phase 3 предпочитает `sklearn Pipeline(StandardScaler(), ElasticNet)`.
   Если это окажется слишком большим вмешательством, fallback - `self.scaler`
   plus explicit transform. До Phase 3 старые profit-test results считаются
   legacy/unverified.

4. `threshold` / `decision_threshold` contract drift.

   Текущие участки:

   - `model_classes.py:145` profit-test читает `threshold`;
   - `model_classes.py:229` и `259` фильтруют только `decision_threshold` перед
     `ElasticNet.set_params(...)`;
   - `model_classes.py:242`, `269`, `286` train metrics используют
     `decision_threshold`;
   - `data/models/new_models/model copy 5.json` содержит `decision_threshold`;
   - `data/models/new_models/example tmps.json` и `data/param_grids/new_grids`
     используют `threshold`.

   Почему это опасно:

   - текущий single-model JSON с `decision_threshold` проходит set_params filter,
     но profit-test может упасть на `self.model_parameters['threshold']`;
   - param-grid JSON с `threshold` может передать `threshold` в
     `ElasticNet.set_params(...)`, где такого параметра нет;
   - metrics и profit-test могут использовать разные threshold sources.

   Диагностический snippet:

   ```python
   ElasticNet().set_params(alpha=1.0, l1_ratio=0.5, threshold=0.2)
   # ValueError: Invalid parameter 'threshold' for estimator ElasticNet()
   ```

   Решение: Phase 4 должна выбрать canonical key. Предварительное решение:
   canonical internal key = `decision_threshold`, old `threshold` принимается
   только через явный compatibility adapter.

5. Debug/runtime artifact writes in predict path.

   Текущие участки:

   - `model_classes.py:151` пишет `data_copy_for_predictions.parquet`;
   - `model_classes.py:170` пишет `data_after_predictions.parquet`;
   - `model_classes.py:38` делает `os.chdir(script_dir)`, поэтому файлы пишутся
     в модульную директорию, а не в run-specific artifact directory.

   Почему это опасно:

   - это может перетирать debug artifacts между runs;
   - это мешает понять, к какому run относится parquet;
   - но это не первичный correctness bug относительно scaler/schema.

   Решение: не трогать в первых correctness patches, кроме случая, если feature
   schema tests потребуют изоляции side effect. Оформить как follow-up или
   отдельную маленькую фазу после core contracts.

6. `merge_asof(..., direction='nearest')` remains a data-alignment follow-up.

   Текущие участки:

   - `data_operations.py:538-544`;
   - `data_operations.py:682-688`.

   Почему не правим сразу:

   - `nearest` может быть частью старой исследовательской логики;
   - включение `tolerance` или обязательного `calculate_in_10_min_period` меняет
     semantic feature generation, а не только технический контракт;
   - это требует отдельной диагностики на реальных windows.

   Решение: не смешивать с Phase 1-4. Пока фиксируем как follow-up после
   восстановления базовых train/predict contracts.

#### Practical next step

Следующий кодовый шаг: Phase 1 only.

Scope Phase 1:

- исправить timestamp filters в `teach_n_test_data_with_basic_corrs(...)` и
  `teach_n_test_data_with_optimized_corrs(...)`;
- добавить focused unit test, который падает на старой форме и проходит на
  исправленной;
- не трогать scaler, schema, threshold и `merge_asof` в этом коммите.

#### Phase 1 implementation blocker - ignored production file

При начале Phase 1 обнаружено, что целевой файл
`modules/teach_and_update_models/data_operations.py` не отслеживается Git и
попадает под правило `.gitignore:46:data_operations.py`.

Проверки:

```bash
git ls-files -v modules\teach_and_update_models\data_operations.py
# no output

git check-ignore -v modules\teach_and_update_models\data_operations.py
# .gitignore:46:data_operations.py
```

Почему это важно:

- timestamp bug находится именно в этом файле;
- обычный `git status` не показывает изменения в ignored файле;
- локальная правка может пройти локальный тест, но не попадет в commit/push;
- `git add -f` мог бы force-track файл, но это нельзя делать молча, потому что
  файл выглядит как legacy/production strategy logic, специально исключенная из
  публичного/обычного Git scope.

Текущее решение:

- скрытая локальная пробная правка в ignored файле была убрана;
- Phase 1 не продолжается как code patch до выбора политики для
  `data_operations.py`;
- безопасные варианты:
  1. force-track конкретный `data_operations.py`, если его допустимо хранить в
     репозитории;
  2. оставить файл private/local и применять Phase 1 как локальный patch без
     Git-фиксации, явно понимая риск невоспроизводимости;
  3. вынести минимальный tracked compatibility layer/helper в отслеживаемый
     модуль и затем вручную подключить его в private `data_operations.py`;
  4. отложить Phase 1 code patch и сначала решить статус ignored production
     ML/data files.

Выбор пользователя:

- выбран вариант 2: оставить `data_operations.py` private/local и делать
  локальные patch-и без Git-воспроизводимости;
- `git add -f` не использовать;
- правки в ignored production file допустимы, потому что локальная копия есть и
  restore point уже зафиксирован;
- все такие изменения нужно подробно описывать в этом документе, чтобы при
  проблемах можно было восстановить ход решений.

### Phase 1 - Timestamp filter correctness

Что:

- Исправить только подтвержденные pandas boolean filters:
  `Timestamp >= start & Timestamp <= end` -> `(Timestamp >= start) & (...)`.
- Добавить pure unit test на маленьком DataFrame, который доказывает, что
  train/profit windows выбираются ожидаемо.

Почему:

- Это локальная correctness-ошибка с низким blast radius, но она может менять
  состав train/profit выборки. Ее нужно закрыть отдельно и проверить отдельно.

Ожидаемый результат:

- Один маленький commit: timestamp filter fix + focused test.

### Phase 1 result - 2026-05-04

Статус: completed locally, not pushed as production code.

#### Что изменено локально

Ignored/private file:

- `modules/teach_and_update_models/data_operations.py`

Локальные изменения:

1. Добавлен pure helper:

   ```python
   def filter_timestamp_window(df, timestamp_column, start_tmsp, end_tmsp):
       return df.loc[
           (df[timestamp_column] >= start_tmsp) &
           (df[timestamp_column] <= end_tmsp)
       ]
   ```

2. В `teach_n_test_data_with_basic_corrs(...)` заменены оба window filters:

   - profit-test window теперь идет через `filter_timestamp_window(...)`;
   - teaching window теперь идет через `filter_timestamp_window(...)`;
   - исправлен ключевой bug: старая форма
     `data_for_teach_df['Timestamp'] >= teaching_start_tmsp & (...)` больше не
     используется.

3. В `teach_n_test_data_with_optimized_corrs(...)` сделана такая же замена:

   - profit-test window через helper;
   - teaching window через helper;
   - logic остается inclusive по границам: `start <= Timestamp <= end`.

Почему helper, а не inline parentheses:

- уменьшается шанс снова ошибиться с приоритетом `&`;
- один focused unit test проверяет общий contract;
- изменение маленькое и не трогает feature generation, scaler, schema,
  threshold или `merge_asof`.

#### Что изменено в tracked tests

Tracked file:

- `tests/unit_smoke/test_correlation_pipeline_contracts.py`

Добавлен тест:

- `test_filter_timestamp_window_includes_only_requested_boundaries`

Смысл теста:

- input timestamps: `900`, `1000`, `1500`, `2000`, `2100`;
- window: `1000-2000`;
- expected rows: `start`, `inside`, `end`;
- строки `before` и `after` исключаются.

#### Проверки

```bash
python -m pytest tests\unit_smoke\test_correlation_pipeline_contracts.py -q
# 3 passed, 1 warning

python -m pytest tests\unit_smoke -q
# 73 passed, 1 warning
```

Warning:

- `DeprecationWarning` в `normalize_amount` / pandas `DataFrameGroupBy.apply`;
- warning старый, не связан с Phase 1 timestamp helper.

#### Git status expectation

- `data_operations.py` не показывается в `git status`, потому что ignored;
- tracked changes видны только в docs/test files;
- production fix сейчас существует только в локальной рабочей копии.

Rollback для Phase 1:

- восстановить локальный `data_operations.py` из личной копии пользователя или
  вручную вернуть old filters;
- tracked docs/test изменения можно откатить отдельно через обычный Git flow,
  если потребуется.

### Phase 2 - Feature schema contract

Что:

- Ввести минимальный helper для feature columns:
  drop target/service columns, preserve order, fail on missing train columns.
- Явно исключить технический `index`, если он появляется как колонка после
  parquet/reset_index/load path.
- Сохранить список train feature columns на model object после fit.
- В predict/profit-test использовать только сохраненные feature columns и
  выбрасывать понятную ошибку при missing columns.

Почему:

- Без schema contract model может обучаться на одном наборе колонок, а
  profit-test предсказывать по другому. Это хуже явного падения, потому что
  результат выглядит численно валидным.

Ожидаемый результат:

- Focused tests:
  - extra `index` column не попадает в prediction features;
  - missing train feature вызывает `ValueError`;
  - порядок колонок восстанавливается по train schema.

### Phase 2 result - 2026-05-04

Статус: completed locally, not pushed.

#### Что изменено

Tracked file:

- `modules/teach_and_update_models/model_classes.py`

Изменения:

1. В `GeneralModel` добавлен список non-feature columns:

   ```python
   NON_FEATURE_COLUMNS = ("Action", "Price", "Predicted_Action", "index")
   ```

   Причина:

   - `Action` - target;
   - `Price` нужен для profit-test accounting, но не должен быть model feature;
   - `Predicted_Action` - output от модели;
   - `index` - техническая колонка после `reset_index(inplace=True)` в ignored
     `data_operations.py`.

2. Добавлен helper:

   ```python
   def prepare_feature_frame(self, data, feature_columns=None):
       feature_frame = data.drop(columns=list(self.NON_FEATURE_COLUMNS), errors="ignore")
       ...
   ```

   Contract:

   - без `feature_columns` возвращает train feature frame после удаления
     non-feature columns;
   - с `feature_columns` проверяет missing columns и возвращает DataFrame в
     train order;
   - extra columns в prediction data игнорируются, если их нет в train schema.

3. В `ElasticNetModel.train_model_specific(...)` train features теперь
   готовятся через `prepare_feature_frame(...)`.

   Эффект:

   - `index` больше не попадает в `X`;
   - `self.model_feature_columns` сохраняет порядок train features;
   - `StandardScaler` пока остается как было, то есть scaler mismatch еще не
     исправлен и остается Phase 3.

4. В `GeneralModel.calculate_total_value(...)` prediction data теперь
   готовится через:

   ```python
   self.prepare_feature_frame(data, self.model_feature_columns)
   ```

   Эффект:

   - predict/profit-test использует тот же список колонок и порядок, что train;
   - если feature из train отсутствует в profit-test data, будет явный
     `ValueError`, а не тихое предсказание на другом наборе признаков.

#### Что изменено в tests

Tracked files:

- `tests/unit_smoke/test_model_feature_contracts.py`
- `tests/unit_smoke/test_correlation_pipeline_contracts.py`

Добавлены focused tests:

- `test_prepare_feature_frame_drops_non_feature_columns_and_preserves_order`;
- `test_prepare_feature_frame_restores_train_order_and_fails_on_missing_features`;
- `test_filter_timestamp_window_includes_only_requested_boundaries`.

#### Проверки

```bash
python -m pytest tests\unit_smoke\test_model_feature_contracts.py tests\unit_smoke\test_correlation_pipeline_contracts.py -q
# 5 passed, 1 warning

python -m pytest tests\unit_smoke -q
# 75 passed, 1 warning
```

Warning:

- тот же старый pandas `DataFrameGroupBy.apply` warning в `normalize_amount`;
- не связан с Phase 2.

#### Что оставалось после Phase 2

- На момент завершения Phase 2 `StandardScaler` mismatch еще не был исправлен:
  train still scaled, predict still called raw model on unscaled features.
  Позже это закрыто в Phase 3.
- На момент завершения Phase 2 `threshold` / `decision_threshold` drift еще не
  был исправлен. Позже это закрыто в Phase 4.
- debug parquet writes в `calculate_total_value(...)` не перенесены. Это
  follow-up после core contracts.
- `data_operations.py` остается ignored/private; Phase 1 fix существует только
  локально.

### Phase 3 - Preprocessing contract

Что:

- Предпочтительный minimal path: заменить связку
  `StandardScaler().fit_transform(...)` + raw `ElasticNet` на sklearn
  `Pipeline([("scaler", StandardScaler()), ("model", ElasticNet(...))])`.
- Альтернатива, если Pipeline ломает слишком много старого кода:
  сохранить `self.scaler` и применять `self.scaler.transform(...)` перед
  predict.
- Не менять модельный алгоритм и параметры, кроме технического переноса scaler
  внутрь единого predict path.

Почему:

- Сейчас train видит scaled features, а profit-test может видеть raw features.
  Это делает profit-test результат недостоверным даже при отсутствии ошибок.

Ожидаемый результат:

- Focused test, где модель обучается и predict вызывается через один и тот же
  preprocessing path.
- Старые profit-test цифры до этой фазы помечаются как legacy/unverified.

### Phase 3 result - 2026-05-04

Статус: completed locally, not pushed.

#### Что изменено

Tracked file:

- `modules/teach_and_update_models/model_classes.py`

Изменения:

1. `ElasticNetModel.train_model_specific(...)` больше не строит отдельный
   `StandardScaler().fit_transform(...)` и raw `ElasticNet`.

2. Вместо этого `self.model` становится sklearn Pipeline:

   ```python
   Pipeline([
       ("scaler", StandardScaler()),
       ("regressor", ElasticNet(max_iter=10000)),
   ])
   ```

3. Train path теперь передает в Pipeline raw feature frame:

   - scaler fit/transform происходит внутри Pipeline;
   - regressor fit получает scaled features через Pipeline internals;
   - `calculate_total_value(...)` вызывает `self.model.predict(...)` на raw
     feature frame, и Pipeline применяет тот же scaler.

4. ElasticNet model params теперь префиксуются для Pipeline:

   - `alpha` -> `regressor__alpha`;
   - `l1_ratio` -> `regressor__l1_ratio`;
   - seed/random_state от `model_params_with_seed(...)` тоже идет в
     `regressor__random_state`.

5. Saved model artifact становится scaler-aware:

   - `save_model(...)` как и раньше делает `dump(model, model_path)`;
   - но `model` теперь Pipeline, поэтому scaler сохраняется вместе с regressor.

Почему выбран Pipeline, а не `self.scaler`:

- отдельный `self.scaler` исправил бы только runtime object;
- saved `.joblib` остался бы raw model без scaler;
- Pipeline делает train/predict/save единым contract object.

#### Что изменено в tests

Tracked file:

- `tests/unit_smoke/test_model_feature_contracts.py`

Добавлен test:

- `test_elasticnet_training_stores_scaler_aware_pipeline`

Что проверяет:

- `train_model_specific(...)` на маленьком synthetic DataFrame завершается;
- `model.model` является `sklearn.pipeline.Pipeline`;
- Pipeline steps: `["scaler", "regressor"]`;
- `model_feature_columns` не содержит `index` и равен
  `["feature_a", "feature_b"]`.

В тесте `pd.DataFrame.to_parquet` monkeypatch-ится в no-op, чтобы unit test не
создавал debug parquet artifacts.

#### Проверки

```bash
python -m pytest tests\unit_smoke\test_model_feature_contracts.py -q
# 5 passed, 1 warning

python -m pytest tests\unit_smoke -q
# 78 passed, 2 warnings
```

Warnings:

- старый pandas warning в `normalize_amount`;
- `UndefinedMetricWarning` в synthetic model test из-за маленького набора и
  отсутствия predicted samples для одного класса. Это тестовый артефакт, а не
  runtime regression.

#### Что остается после Phase 3

- Нужно решить, хотим ли явно подавлять/настраивать `zero_division` в metrics.
  Это не входит в текущую correctness правку.
- Debug parquet writes в `calculate_total_value(...)` все еще пишутся в module
  cwd. Это отдельный artifact hygiene follow-up.
- Старые model/profit-test результаты до Phase 1-4 считать legacy/unverified.

### Phase 4 - Threshold contract

Что:

- Разобрать текущие значения:
  - `calculate_total_value(...)` читает `threshold`;
  - train metrics читают `decision_threshold`;
  - param filtering исключает только `decision_threshold`.
- Выбрать один canonical key, предпочтительно `decision_threshold` для
  превращения continuous prediction в action.
- Если старые model json используют `threshold`, добавить явный adapter:
  принимать старое имя, но внутри нормализовать к canonical key.

Почему:

- Разные threshold keys могут давать разные actions в metrics и profit-test.
  Это напрямую ломает доверие к сравнению моделей.

Ожидаемый результат:

- Test на backward-compatible normalization.
- Predict/profit-test и train metrics используют один threshold source.

### Phase 4 result - 2026-05-04

Статус: completed locally before Phase 3 as an unblocker, not pushed.

Почему Phase 4 выполнена до Phase 3:

- `train_model_specific(...)` внутри training flow вызывает
  `calculate_total_value(...)`;
- `calculate_total_value(...)` до правки читал `threshold`;
- текущий рабочий `data/models/new_models/model copy 5.json` использует
  `decision_threshold`;
- значит Phase 3 preprocessing/scaler нельзя было надежно тестировать, пока
  threshold drift не убран.

#### Что изменено

Tracked file:

- `modules/teach_and_update_models/model_classes.py`

Изменения:

1. `GeneralModel.__init__(...)` теперь нормализует `model_param` через
   `normalize_model_parameters(...)`.

2. Backward compatibility:

   - старый config key `threshold` принимается;
   - внутри он превращается в canonical key `decision_threshold`;
   - старый key удаляется из `self.model_parameters`, чтобы не попасть в
     `ElasticNet.set_params(...)`.

3. Conflict behavior:

   - если одновременно заданы `threshold` и `decision_threshold` с разными
     значениями, constructor падает с `ValueError`;
   - это лучше, чем тихо выбрать одно значение и получить непонятный profit-test.

4. `calculate_total_value(...)` теперь читает только:

   ```python
   self.model_parameters["decision_threshold"]
   ```

#### Что изменено в tests

Tracked file:

- `tests/unit_smoke/test_model_feature_contracts.py`

Добавлены tests:

- `test_model_parameters_normalize_legacy_threshold_to_decision_threshold`;
- `test_model_parameters_reject_conflicting_threshold_names`.

#### Проверки

```bash
python -m pytest tests\unit_smoke\test_model_feature_contracts.py -q
# 4 passed

python -m pytest tests\unit_smoke -q
# 77 passed, 1 warning
```

Warning:

- старый pandas warning в `normalize_amount`;
- не связан с threshold normalization.

#### Phase 3 dependency resolved

- Этот блок был выполнен раньше Phase 3 только как unblocker.
- После Phase 3 `StandardScaler` уже находится внутри sklearn `Pipeline`.
- Saved model artifact теперь scaler-aware, потому что `self.model` сохраняется
  как `Pipeline([("scaler", StandardScaler()), ("regressor", ElasticNet(...))])`.

### Phase 5 - Narrow runtime verification

Что:

- Запустить focused unit tests по измененным контрактам.
- Затем запустить `python -m pytest tests\unit_smoke -q`.
- Не запускать тяжелый full pipeline на больших данных до обсуждения
  validation scenario.

Почему:

- Unit tests ловят контрактные ошибки быстро; full pipeline может быть дорогим
  и смешать несколько причин изменения результата.

Ожидаемый результат:

- Зеленые narrow checks.
- Если full scenario нужен, сначала отдельно выбрать маленькое окно/TEST mode.

### Phase 5 result - 2026-05-04

Статус: completed locally for unit/smoke scope, not pushed.

Проверки после Phase 1, Phase 2, Phase 4 и Phase 3:

```bash
python -m pytest tests\unit_smoke\test_correlation_pipeline_contracts.py -q
# 3 passed, 1 warning

python -m pytest tests\unit_smoke\test_model_feature_contracts.py -q
# 5 passed, 1 warning

python -m pytest tests\unit_smoke -q
# 78 passed, 2 warnings
```

Warnings:

- pandas `DataFrameGroupBy.apply` warning в `normalize_amount`;
- sklearn `UndefinedMetricWarning` в synthetic Pipeline test из-за маленького
  тестового dataset.

Оба warning-а не являются новыми runtime failures. Их можно разобрать позже,
но они не блокируют текущие correctness fixes.

Что не запускалось:

- полный `main-pipeline` на реальных данных;
- тяжелые SQLite/data collection сценарии;
- profit-test на историческом model window.

Причина:

- текущий этап был про локальные contracts и unit smoke;
- полный runtime scenario может быть дорогим и смешает correctness fix с
  внешними side effects: Flask start, price update, peaks update, SQLite/Dask
  collection.

Перед полным runtime validation нужно отдельно выбрать маленькое окно или
контролируемый TEST-mode scenario.

### Runtime validation logging plan - 2026-05-04

Цель перед первым запуском `main-pipeline` после fixes:

- не только увидеть `success/error`, но и понять, где именно изменилось
  поведение данных, признаков, модели и profit-test;
- иметь достаточно информации в `logs/<run_id>.log` и
  `logs/agent_runs/<run_id>/events.jsonl`, чтобы не восстанавливать картину по
  памяти.

#### Existing logger/run_tracker coverage

Уже есть:

- `run_started` / `run_finished`;
- `run_metadata` с:
  - git commit hash;
  - args;
  - python/pandas/dask/sklearn versions;
  - paths;
  - model params после `train_new_model_from_json(...)`;
- stages:
  - `features.correlation_data`;
  - `train.model_fit`;
  - `evaluate.profit_test`;
  - `artifact.model_save`;
- stage duration/status/details.

Этого хватает для ответа "на каком stage упало", но не хватает для ответа
"какие данные и feature contracts реально попали в модель".

#### Added local diagnostic logs

Статус: added locally, not pushed.

Tracked files:

- `modules/teach_and_update_models/orchestrator.py`;
- `modules/teach_and_update_models/model_classes.py`.

Новые log markers:

1. `PIPELINE_DATA_SUMMARY`

   Где:

   - после `get_corelation_by_tmsp_df(...)` до `clean_data(...)`;
   - после `clean_data(...)` для train/profit-test frames.

   Что пишет:

   - `name`: `train_raw_before_clean`, `profit_raw_before_clean`,
     `train_after_clean`, `profit_after_clean`;
   - `rows`;
   - `columns_count`;
   - `columns`;
   - `timestamp_min` / `timestamp_max`, если `Timestamp` еще есть;
   - `action_counts`, если `Action` есть.

   Зачем:

   - увидеть, что timestamp windows реально отрезали ожидаемые диапазоны;
   - увидеть, что `clean_data(...)` не удалил нужные признаки;
   - увидеть, что `Action` не стал all-zero или перекошенным неожиданно.

2. `MODEL_CONTRACT`

   Где:

   - после подготовки train feature frame;
   - перед profit-test predict.

   Что пишет:

   - `context`: `train_features_prepared` или `profit_predict`;
   - `model_type`;
   - `decision_threshold`;
   - `feature_count`;
   - `feature_columns`;
   - `model_object_type`;
   - `pipeline_steps`;
   - row/column counts для train/predict feature frame.

   Зачем:

   - подтвердить, что `index` не попал в features;
   - подтвердить одинаковый feature count/order между train и predict;
   - подтвердить, что model object - `Pipeline`, а не raw `ElasticNet`;
   - подтвердить active threshold.

3. `MODEL_PREDICTION_SUMMARY`

   Где:

   - после расчета `Predicted_Action` в `calculate_total_value(...)`.

   Что пишет:

   - rows;
   - threshold;
   - `predicted_action_counts`.

   Зачем:

   - быстро увидеть all-cash/all-hold behavior;
   - понять, генерирует ли модель реальные buy/sell signals;
   - отличить "profit плохой из-за рынка" от "модель почти ничего не делает".

#### What to inspect after running `main-pipeline`

1. Найти новый `run_id`:

   - по консольному warning `Старт main.py, прогон № <id>`;
   - или по новому файлу `logs/<id>.log`;
   - или по `logs/agent_runs/<id>/manifest.json`.

2. Проверить run status:

   - `logs/agent_runs/<id>/summary.json`;
   - `_TRACKER_INFO event=run_finished` в `logs/<id>.log`.

3. Проверить stage durations:

   - `features.correlation_data`;
   - `train.model_fit`;
   - `evaluate.profit_test`;
   - `artifact.model_save`.

4. Проверить data contracts:

   - `PIPELINE_DATA_SUMMARY name=train_raw_before_clean`;
   - `PIPELINE_DATA_SUMMARY name=profit_raw_before_clean`;
   - `PIPELINE_DATA_SUMMARY name=train_after_clean`;
   - `PIPELINE_DATA_SUMMARY name=profit_after_clean`.

5. Проверить model contracts:

   - `MODEL_CONTRACT context=train_features_prepared`;
   - `MODEL_CONTRACT context=profit_predict`;
   - feature columns должны совпадать по count/order;
   - `pipeline_steps` должны быть `["scaler", "regressor"]`.

6. Проверить prediction behavior:

   - `MODEL_PREDICTION_SUMMARY`;
   - если `predicted_action_counts` почти весь `0`, profit-test может быть
     фактически all-cash;
   - если нет `1` или `-1`, это не обязательно bug, но требует отдельного
     анализа threshold/model signal.

#### Recommendation before running full main-pipeline

Сначала запустить обычный `main-pipeline` только если готовы к его side effects:

- Flask start;
- price update;
- peaks update;
- SQLite/Dask feature collection;
- model/profit artifacts.

Если хотим максимально контролируемую проверку, лучше сначала добавить или
использовать TEST-mode для main pipeline. Сейчас `main-pipeline` вызывает
`train_new_model_from_json(TEACHING_TEST=0)`, то есть не sample mode.

Минимально полезный run record после запуска:

- command;
- run_id;
- final status;
- stage durations;
- train/profit rows before/after clean;
- timestamp ranges;
- feature_count and feature_columns;
- decision_threshold;
- pipeline_steps;
- predicted_action_counts;
- final profit value from `evaluate.profit_test`;
- saved model path.

### Runtime validation attempt 97 - 2026-05-04

Command:

```bash
python main.py main-pipeline
```

Result:

- run_id: `97`;
- status: `error`;
- duration: `00:00:04`;
- failed before ML feature/train/profit-test stages;
- failure point: `update_btc_price_data()` ->
  `raw_prices_cleaning.clean_raw_data()` -> `get_price_data(...)`.

Error:

```text
404 Client Error: Not Found for url:
https://api.binance.com/api/v3/klines/api/v3/klines?symbol=BTCUSDT...
RuntimeError: Не получилось обновить данные BTC из внешнего источника.
```

Diagnosis:

- `settings.price_updater.BINANСE_API_URL` already contained
  `/api/v3/klines`;
- `modules/bts_price_updater/price_updater.py` added `/api/v3/klines` again;
- final URL duplicated endpoint path and Binance returned 404.

Fix:

- `settings/price_updater.py` now stores base URL:
  `https://api.binance.com`;
- `price_updater.py` remains responsible for adding `/api/v3/klines`;
- added smoke test:
  `tests/unit_smoke/test_price_updater.py::test_get_price_data_uses_single_binance_klines_endpoint`.

Checks:

```bash
python -m pytest tests\unit_smoke\test_price_updater.py -q
# 1 passed

python -m pytest tests\unit_smoke -q
# 79 passed, 2 warnings
```

Next runtime step:

- rerun `python main.py main-pipeline`;
- if price update succeeds, inspect the new run for `PIPELINE_DATA_SUMMARY`,
  `MODEL_CONTRACT`, and `MODEL_PREDICTION_SUMMARY`.

### Runtime validation attempt 104 - 2026-05-04

Command:

```bash
python main.py main-pipeline
```

Result:

- run_id: `104`;
- status: `error`;
- duration: `00:24:31`;
- price update and peak preparation passed;
- failure point: `features.correlation_data`, after Dask correlation work had
  been running for about 8 minutes.

Error:

```text
ValueError: Unsupported correlation_type: 0.2
```

Diagnosis:

- model config passes `correlation_type='basic'` and
  `correlation_threshold=0.2`;
- inside ignored/private
  `modules/teach_and_update_models/data_operations.py`, the nested Dask worker
  called `calculate_correlations_of_wallets(...)` with positional arguments;
- the function signature is
  `calculate_correlations_of_wallets(data, correlation_threshold=None, correlation_type=None)`;
- the old positional call could pass `0.2` into `correlation_type`, so the
  function rejected the numeric threshold as an unsupported correlation type;
- Dask worker/nanny warnings after the exception were secondary cleanup noise
  after the root task failed.

Fix:

- changed the ignored/private Dask worker call to keyword arguments:
  `correlation_threshold=correlation_threshold` and
  `correlation_type=correlation_type`;
- added a focused smoke test that guards this local contract without launching
  the heavy SQL/Dask runtime path;
- changed noisy TODO `logger.warning(...)` calls to `logger.info(...)`;
- changed the BTC price resample alias from deprecated `T` to `min`;
- changed `normalize_amount(...)` to pandas `include_groups=False` and restored
  `Wallet_id` from the groupby index, removing the pandas deprecation warning
  while preserving the normalized output contract.

Checks:

```bash
python -m pytest tests\unit_smoke\test_correlation_pipeline_contracts.py -q
# 4 passed

python -m pytest tests\unit_smoke\test_model_feature_contracts.py tests\unit_smoke\test_price_updater.py -q
# 6 passed, 1 warning

python -m pytest tests\unit_smoke -q
# 80 passed, 1 warning
```

Remaining warning:

- `sklearn.metrics.UndefinedMetricWarning` appears only in a small model smoke
  test where the synthetic dataset does not produce every class; it is not the
  main pipeline warning from run 104.

### Runtime validation attempt 105 - 2026-05-04

Command:

```bash
python main.py main-pipeline
```

Result:

- run_id: `105`;
- status: `error`;
- duration: `00:45:38`;
- run passed the previous `Unsupported correlation_type: 0.2` failure;
- failure point: `features.correlation_data`, after Parquet/Dask data was
  already built and passed into `get_data_for_teach_with_dask(...)`.

Console warning before failure:

```text
distributed.worker.memory - WARNING - Unmanaged memory use is high.
Unmanaged memory: 5.80 GiB -- Worker memory limit: 7.45 GiB
```

Root error:

```text
TypeError: Ожидался pandas DataFrame, Dask DataFrame или Future,
а получен тип <class 'dask.dataframe.core.DataFrame'>.
```

Diagnosis:

- the memory warning is important and means the Dask worker was close to its
  memory limit;
- however, the concrete run failure was not an out-of-memory kill;
- the code threw a local `TypeError` in
  `ensure_dask_dataframe(...)`;
- the object was already a Dask DataFrame, but from the legacy/core class:
  `dask.dataframe.core.DataFrame`;
- in the current local Python/Dask environment, `dd.DataFrame` points to
  `dask_expr._collection.DataFrame`;
- therefore `isinstance(obj, dd.DataFrame)` can reject a valid Dask DataFrame
  when the pipeline sees a different Dask backend/class.

Fix:

- added `is_dask_dataframe_like(...)` in ignored/private
  `modules/teach_and_update_models/data_operations.py`;
- it accepts:
  - current `dd.DataFrame`;
  - legacy `dask.dataframe.core.DataFrame`;
  - objects with the Dask DataFrame interface used by the pipeline:
    `compute`, `npartitions`, `map_partitions`;
- `ensure_dask_dataframe(...)` now uses this compatibility helper.

Checks:

```bash
python -m pytest tests\unit_smoke\test_correlation_pipeline_contracts.py -q
# 6 passed

python -m pytest tests\unit_smoke -q
# 82 passed, 1 warning
```

Memory note:

- this fix addresses the immediate type-check crash;
- it does not reduce Dask memory use;
- if the next run proceeds further but keeps warning about unmanaged memory,
  memory behavior needs a separate performance/safety pass before changing
  chunk sizes, persist strategy, worker limits, or Parquet partitioning.

### Dask compatibility hardening - 2026-05-04

Reason:

- run `105` exposed a Dask backend compatibility issue:
  `dask.dataframe.core.DataFrame` was a valid Dask DataFrame, but the local
  type check expected the current `dd.DataFrame` class;
- current local runtime uses Dask `2024.5.2`, where `dd.DataFrame` resolves to
  `dask_expr._collection.DataFrame`;
- future Dask upgrades should not depend on one concrete backend class.

Scope:

- safe local compatibility changes only;
- no SQLite mutation;
- no index rebuild;
- no full `main-pipeline` rerun from the agent;
- no attempt to solve the Dask memory architecture in this patch.

Changes:

- `modules/teach_and_update_models/data_operations.py`:
  - `is_dask_dataframe_like(...)` now uses Dask collection/interface checks
    instead of only `isinstance(obj, dd.DataFrame)`;
  - `ensure_dask_dataframe(...)` keeps accepting pandas, Future, current Dask
    DataFrame, legacy/core Dask DataFrame, and Dask-like dataframe objects;
  - `process_chunk(...)` is no longer double-wrapped with `@delayed` and
    `delayed(process_chunk)(...)`;
  - the chunk stage now logs `successful_chunks` / `total_chunks`;
  - empty chunk output is detected from delayed task results instead of
    `len(all_txs_of_wallets_ddf)`, avoiding an expensive Dask row-count
    computation;
  - correlation temp parquet directories are cleared before writing new chunk
    output, but only under the module runtime temp directory.
- `modules/teach_and_update_models/model_classes.py`:
  - profit-test Dask input detection now uses the same Dask-like contract via
    `data_operations.is_dask_dataframe_like(...)`;
  - this prevents another backend-specific `dd.DataFrame` check from failing
    later in the chain.
- `tests/unit_smoke/test_correlation_pipeline_contracts.py`:
  - added coverage for Dask-like dataframe detection;
  - added coverage for runtime parquet cleanup guard;
  - added static guard against nested delayed and expensive Dask `len(...)`
    empty checks.

Design review summary:

- Minimal compatibility patch:
  - chosen now;
  - fixes current crash and likely next backend-class issue;
  - low data risk, no database writes;
  - rerun-safe because stale parquet files are cleared before new chunk output.
- Production-oriented Dask refactor:
  - replace pandas chunk SQL extraction + temp parquet + global sort/persist
    with a clearer Dask collection pipeline;
  - likely faster and lower memory in the long term;
  - needs separate design and validation because it changes the execution
    shape of the feature pipeline.
- Workaround:
  - pin old Dask or suppress memory/type warnings;
  - rejected as default because it hides compatibility problems and does not
    improve reproducibility.
- Long-term architecture:
  - push more filtering/windowing closer to SQLite/Parquet partitions and
    persist reusable intermediate artifacts with run metadata;
  - best maintainability, but too large for the current correctness patch.

Checks:

```bash
python -m pytest tests\unit_smoke\test_correlation_pipeline_contracts.py -q
# 8 passed

python -m pytest tests\unit_smoke\test_model_feature_contracts.py -q
# 5 passed, 1 warning

python -m pytest tests\unit_smoke -q
# 84 passed, 1 warning
```

Remaining memory risk:

- `txs_ddf.sort_values('Block_time').persist()` can still be expensive;
- `dd.merge_asof(...)` requires sorted data and may remain memory-heavy;
- Dask unmanaged-memory warnings should be treated as a performance/design
  follow-up, not just console noise.

### Dask runtime profile and observability - 2026-05-04

Reason:

- run after compatibility hardening still showed worker instability/noise:
  unregistered worker heartbeat, lost computed tasks, and unmanaged-memory
  warnings around 5.2-5.6 GiB on a 7.45 GiB worker limit;
- user stopped the run manually and selected the medium stability profile.

Chosen profile:

- `total_memory='24GB'`;
- `n_workers=2`;
- `threads_per_worker=2`;
- main teaching `chunk_size=90` instead of `180`.

Why:

- the machine has about 32 GB RAM;
- `24GB` gives Dask more headroom while leaving memory for Windows, Python
  parent process, SQLite, filesystem cache, and Flask;
- fewer worker threads reduce simultaneous pandas-heavy work inside each worker;
- smaller wallet chunks reduce the size of each SQLite -> pandas -> parquet
  task.

Changes:

- `modules/dask_client_init/get_dask_client.py`:
  - default client profile changed to `24GB / 2 workers / 2 threads`;
  - logs `DASK_CLIENT_PROFILE` with memory/thread/settings data;
  - logs `DASK_CLUSTER_SNAPSHOT` after client start and before close;
  - `wait_for_all_tasks(...)` now refreshes scheduler task state inside the
    polling loop instead of reusing one stale snapshot.
- `modules/teach_and_update_models/orchestrator.py`:
  - main pipeline `chunk_size` changed from `180` to `90`.
- `modules/teach_and_update_models/data_operations.py`:
  - added `DASK_DATAFRAME_STATE` logs around:
    - parquet read outputs;
    - `ensure_dask_dataframe(...)`;
    - wallet/correlation merge;
    - `sort_values('Block_time').persist()`;
  - these logs record type, partitions, columns, and divisions metadata without
    triggering row-count computations.

How to use the new logs:

- `DASK_CLIENT_PROFILE` answers "what profile did this run actually use?";
- `DASK_CLUSTER_SNAPSHOT` helps see worker count, threads, memory limit, and
  available worker metrics at lifecycle points;
- `DASK_DATAFRAME_STATE` helps locate where partition count/type/columns change;
- Dask worker-memory warnings still matter, but now they can be compared with
  exact pipeline transitions.

Checks:

```bash
python -m pytest tests\unit_smoke\test_correlation_pipeline_contracts.py -q
# 8 passed

python -m pytest tests\unit_smoke -q
# 84 passed, 1 warning

python -m py_compile modules\dask_client_init\get_dask_client.py modules\teach_and_update_models\data_operations.py modules\teach_and_update_models\orchestrator.py
# passed
```

### Dask load tuning plan - 2026-05-04

Detailed experiment record:

- `docs/experiments/main_pipeline_dask_load_tuning_2026-05-04.md`

Goal:

- find a stable and reasonably fast load profile for `process_chunk` without
  changing feature formulas, labels, timestamp windows, or model params.

Baseline/cautious profile:

- `total_memory='24GB'`;
- `n_workers=2`;
- `threads_per_worker=2`;
- `chunk_size=90`.

Current tuning baseline after run `148` / active run `150`:

- `chunk_size=150`;
- current run profile: `24GB / 2 workers / 2 threads`;
- next-run profile already staged in settings:
  `24GB / 4 workers / 2 threads`;
- run `150` live dashboard sample during `process_chunk`:
  `workers=2`, `cores=4`, `idle=0`, `processing=6`, `tasks=1436`,
  `erred=0`;
- observed worker memory is still well below the 12GB per-worker limit, so the
  next tuning axis is parallelism, not memory reduction.

Optimization order:

1. Finish the active `run 150` first; do not interpret speed until correctness
   is known and the `merge_asof` parquet checkpoint has been reached.
2. Trial C1, next run: `24GB / 4 workers / 2 threads`,
   `chunk_size=150`.
3. If C1 is stable and memory remains below roughly 70% of worker limit, try
   more worker processes before adding threads:
   `24GB / 6 workers / 2 threads`, `chunk_size=150`.
4. If C2 is stable and CPU is still not saturated, consider
   `24GB / 8 workers / 2 threads`, but only if per-worker memory does not get
   close to the limit and SQLite read contention does not appear.
5. If increasing workers causes SQLite contention, worker churn, or too much
   scheduler/process overhead, rollback to the last stable worker count and try
   `+1 thread` instead:
   `24GB / 4 workers / 3 threads`, `chunk_size=150`.
6. Only after the best stable Dask worker/thread shape is found, revisit
   `chunk_size` (`180`, then maybe `220`) to reduce task/parquet-file overhead.
7. Stop when the next tier gives little or no `features.correlation_data`
   improvement, or when instability appears.

Testing ladder:

| Step | Profile | Chunk | What this tests | Next if stable |
| --- | --- | --- | --- | --- |
| Current | `24GB / 2w / 2t` | `150` | corrected checkpoint path under current load | C1 |
| C1 | `24GB / 4w / 2t` | `150` | doubles task slots from 4 to 8 | C2 |
| C2 | `24GB / 6w / 2t` | `150` | more processes for pandas-heavy tasks | C3 or fallback |
| C3 | `24GB / 8w / 2t` | `150` | upper worker-count tier on this machine | stop or chunk-size tier |
| F1 | `24GB / 4w / 3t` | `150` | fallback if more workers hurt SQLite/overhead | compare with C1/C2 |
| A3 | best stable profile | `180` | fewer chunks/parquet files after concurrency is tuned | A4 or stop |
| A4 | best stable profile | `220` | higher chunk-size ceiling | stop unless clearly faster |

Go/no-go:

- Go:
  - no Python traceback;
  - no repeated worker restarts / killed worker symptoms;
  - no unmanaged-memory warnings close to worker limit;
  - no visible SQLite read contention symptoms or long gaps with low Dask
    processing;
  - `features.correlation_data` duration improves or remains acceptable.
- No-go:
  - `KilledWorker`, nanny restarts, repeated recomputation, or memory warnings
    near the worker limit;
  - worker memory above roughly 70% of limit during `process_chunk`;
  - more workers increase runtime or leave workers idle;
  - rollback to the last stable profile.

Metrics to record after each full/live run:

- run id and command;
- Dask profile from `DASK_CLIENT_PROFILE`;
- `successful_chunks` / `total_chunks`;
- `features.correlation_data` duration;
- whether `merged_after_asof_checkpoint_read_parquet` was reached;
- worker count, threads, peak memory, spill, restarts, and dashboard counts
  (`idle`, `processing`, `tasks`, `erred`);
- final run status and traceback summary if failed.

Current decision:

- correctness still gates speed claims: the active run must prove the parquet
  checkpoint fixes the `MergeAsof.how` failure;
- next run should use the staged `24GB / 4 workers / 2 threads` profile;
- after that, prefer increasing worker count before adding threads, because
  the current workload is pandas/SQLite-heavy and memory headroom is available.
- note: the experiment rules were created for the current/old data collection
  method. After changing the collection method, rerun `main-pipeline`, observe
  the new behavior, and restart the optimal-load experiment from a fresh
  baseline.

### Deferred collector contract plan - moved to iteration 15

The future plan for changing the main data collection algorithm through a
`legacy` / `wallet-stats` collector contract has been moved out of iteration 14.

New planning file:

- `docs/iterations/iteration_15.md`

Reason:

- iteration 14 should stay focused on current main pipeline correctness and one
  successful full baseline run;
- changing the collection algorithm touches SQLite, large data, Dask execution
  shape, temp artifacts, and future param-grid behavior;
- this needs its own design review and should not be mixed into the current
  correctness/debugging iteration.

### Project venv synchronization - 2026-05-04

Context:

- the project `.venv` was older than the working global Python environment:
  - `.venv`: Python `3.11.9`, Dask `2023.5.1`, no `dask-expr`;
  - working global Python: Python `3.12.2`, Dask `2024.5.2`;
- run `107` reached past `process_chunk`, but failed later inside the Dask
  train/profit data assembly path with:
  - `'DataFrame' object has no attribute 'unique_partition_mapping_columns_from_shuffle'`;
- this made environment reproducibility part of the current correctness work.

Action taken:

- renamed the old project environment to local backup:
  - `.venv_py311_backup_20260504_203027`;
- recreated `.venv` with Python `3.12.2`;
- installed `requirements.lock.txt`;
- removed `dask-expr` from the project `.venv` and from
  `requirements.lock.txt`;
- explicitly disabled Dask dataframe query-planning before importing
  `dask.dataframe`:
  - `settings.dask.configure_dask_dataframe_backend()`;
  - `dataframe.query-planning=False`;
- verified that `dask.dataframe` now uses the classic backend:
  - `dask.dataframe.core.DataFrame`;
- kept `scripts/update_requirements_lock.py` from hiding installed packages;
  if `dask-expr` appears again in the environment, lock generation should make
  that visible instead of silently excluding it;
- regenerated `requirements.lock.txt`;
- added `.venv_*/` to `.gitignore` so local backup environments are not
  accidentally tracked.

Validation:

- `.venv\Scripts\python.exe -m pip check`:
  - passed, no broken requirements;
- `.venv\Scripts\python.exe -m py_compile` for Dask/model runtime modules:
  - passed;
- `.venv\Scripts\python.exe -m pytest tests\unit_smoke -q`:
  - `85 passed, 1 warning`;
  - warning is the known synthetic sklearn precision warning in
    `test_model_feature_contracts.py`.

Decision:

- treat the recreated `.venv` as the intended project runtime for the next
  checks;
- prefer classic Dask dataframe over `dask-expr` for the current baseline run;
- do not upgrade all packages to latest in the same step;
- first validate the pipeline on the synchronized Python `3.12` environment,
  then plan a separate "latest dependency stack" experiment if needed.

### Latest dependency stack update - 2026-05-04

Detailed experiment record:

- `docs/experiments/dependency_upgrade_audit_2026-05-04.md`

Reason:

- the project started on older package versions;
- current main-pipeline failures were partly Dask/dataframe compatibility
  related;
- before continuing full scenario runs, the project runtime should be
  reproducible on the current Python `3.12.2` stack.

Pre-upgrade safety work:

- added focused smoke contracts for:
  - Dask dataframe backend compatibility;
  - parquet / `merge_asof` / groupby path;
  - pandas resample/groupby behavior;
  - sklearn `Pipeline(StandardScaler(), ElasticNet())`;
  - core package imports.

Action taken:

- created isolated `.venv_upgrade_latest`;
- upgraded the scientific/runtime stack there first;
- verified tests before touching the project `.venv`;
- backed up the previous Python `3.12` project environment locally:
  - `.venv_py312_pre_latest_backup_20260504_220339`;
- recreated project `.venv` from updated `requirements.lock.txt`.

Key versions now locked:

- Dask / distributed: `2026.3.0`;
- pandas: `3.0.2`;
- pyarrow: `24.0.0`;
- numpy: `2.4.4`;
- scipy: `1.17.1`;
- scikit-learn: `1.8.0`;
- numba: `0.65.1`.

Important Dask decision:

- Dask `2026.3.0` no longer supports the legacy/classic dataframe backend;
- `settings.dask` now sets `dataframe.query-planning` by Dask version:
  - Dask before `2025`: classic-compatible `False`;
  - Dask `2025+`: current query-planning path `True`;
- this reverses the earlier "classic only" assumption because latest Dask makes
  it impossible to keep that contract.

Fresh-install issue found and fixed:

- `nbconvert==7.17.1` depends on `bleach[css]`;
- `bleach[css]==6.3.0` requires `tinycss2<1.5`;
- therefore `tinycss2` is intentionally pinned to `1.4.0` instead of latest
  `1.5.1`.

Validation:

```bash
.venv\Scripts\python.exe -m pip check
# No broken requirements found.

.venv\Scripts\python.exe -m pytest tests\unit_smoke -q
# 90 passed, 2 warnings
```

Smoke-test idea:

- Add/keep a focused dependency smoke that verifies packages from
  `requirements.lock.txt` are installed in the active environment, with
  `pip check` as the resolver-consistency check and explicit imports for the
  pipeline-critical libraries.

Known warnings:

- Dask/distributed imports still emit a `pynvml` deprecation warning;
- the synthetic ElasticNet test still emits a known sklearn precision warning.

Current decision:

- use the updated `.venv` for the next `main-pipeline` attempt;
- do not resume Dask load tuning until the updated runtime gets at least one
  successful full `main-pipeline` run or a clearly diagnosed failure point.

### Main pipeline runs after dependency upgrade - 2026-05-04

Run `109`:

- command:
  - `.venv\Scripts\python.exe main.py main-pipeline`;
- environment metadata:
  - Python `3.12.2`;
  - pandas `3.0.2`;
  - Dask `2026.3.0`;
  - sklearn `1.8.0`;
- first Dask block `get_uniq_wallets_of_blocks_with_dask` completed without
  worker memory failure:
  - `spilled_bytes` stayed `0`;
  - no `KilledWorker`;
  - no heartbeat failure;
- the run failed later in `process_chunk` with:
  - `ValueError: assignment destination is read-only`;
  - location: `data_operations.import_peak_intervals`;
  - cause: pandas 3 / numpy view behavior made assignment into
    `Series.values` unsafe.

Fix:

- `import_peak_intervals` now sorts with `.copy()`;
- interval marker arrays are created via `to_numpy(copy=True)`;
- added focused test:
  - `test_import_peak_intervals_uses_writeable_interval_arrays`.

Run `110`:

- started after the pandas 3 fix;
- stopped manually while still in first Dask block
  `get_uniq_wallets_of_blocks_with_dask`;
- reason:
  - the same machine was being used for gaming;
  - this makes performance and worker-stability conclusions noisy;
  - stop was intentional, not a pipeline crash.

Important interpretation:

- run `109` is useful as a compatibility failure diagnosis;
- run `110` should not be used for performance or stability conclusions.

### Main pipeline smoke runner - 2026-05-04

Reason:

- full `main-pipeline` is too expensive to use as the only compatibility check
  after a dependency upgrade;
- we need a fast smoke path that still executes the real `main-pipeline`
  control flow.

Chosen approach:

- do not add a new production scenario yet;
- use a helper script that temporarily rewrites the active model JSON to short
  day-based windows, runs ordinary `main.py main-pipeline`, then restores the
  original JSON.

Command:

```bash
.venv\Scripts\python.exe scripts\run_main_pipeline_smoke.py --days 7
```

What this does:

- finds the single non-example JSON in `data/models/new_models`;
- writes a temporary smoke config with:
  - `training_data_duration_days`;
  - `profit_test_days`;
  - `model_relevance_period_days=0`;
  - month windows set to `0`;
- runs:
  - `main.py main-pipeline`;
- restores the original JSON in `finally`.

Limits:

- this is a compatibility smoke, not a product-ready ML validation;
- it still reads the live SQLite DB and writes normal runtime/model artifacts;
- it should not be used for speed tuning while the machine is under unrelated
  load.

Tech debt:

- after the dependency upgrade, all runtime scenarios need planned validation:
  - `main-pipeline` full run;
  - `param-grid` with a small `--test-fraction`;
  - `test downloaded-from-btc-data` on explicit known blocks;
  - parser monitor startup separately, without turning it into an endless
    unattended run.
- `--start_parser` should not be bundled into generic "run all scenarios"
  automation because it is a long-running monitor and touches external services.

### Phase 6 - Closeout

Что:

- Обновить iteration doc:
  - какие контракты исправлены;
  - какие проверки прошли;
  - какие старые результаты считаются legacy/unverified;
  - README impact.
- Если изменились публичные команды, runtime сценарии, logs/artifacts или
  known limits, обновить README в этой же итерации.

Почему:

- Эта итерация меняет доверие к результатам модели; это нужно оставить как
  понятный инженерный след, а не только как diff в коде.

Ожидаемый результат:

- Итерация закрывается только после маленьких проверяемых commits, а не одним
  большим ML rewrite.

### Порядок работы на практике

1. Найти конкретные участки train/predict/profit-test, где нарушаются
   preprocessing, feature schema, timestamp и threshold contracts.
2. Сделать диагноз с file/line ссылками и выбрать точечные правки.
3. Исправить только подтвержденные correctness issues.
4. Добавить узкие тесты на новые контракты.
5. Запустить narrow verification; для широких runtime/CLI изменений -
   `python -m pytest tests\unit_smoke -q`.
6. Зафиксировать README impact перед closeout.

### Refactor entry check

Для начала итерации или существенной фазы, где мы перерабатываем существующий
код, сначала нужен короткий logic trace до патча.

Формат:

- caller responsibility;
- callee responsibility;
- duplicated responsibility;
- dead or unclear code;
- observable contract;
- narrow verification.

Зачем:

- сначала найти реальные точки приложения усилий;
- не удалять старые ветки кода только потому, что они выглядят лишними;
- отделить redundant code от защитной проверки или старого fallback.

Когда не применять:

- новый код с понятной ответственностью;
- smoke tests;
- техническая документация;
- формат логов;
- argparse/help text;
- маленькие pure-function tests;
- другие узкие локальные задачи, где границы ответственности уже понятны.

### Dask merge_asof follow-up - 2026-05-05

Контекст:

- после обновления до Dask/distributed `2026.3.0` run `141` прошел сбор
  correlation chunks:
  - `successful_chunks=237 total_chunks=237`;
  - затем упал в `features.correlation_data`;
  - ошибка: `'MergeAsof' object has no attribute 'how'`;
- минимальный локальный пример `dd.merge_asof(..., direction="nearest")` на
  Dask `2026.3.0` работает;
- значит, проблема вероятнее всего в конкретном graph shape:
  `merge_asof -> assign/drop -> groupby.agg -> merge -> compute`, а не в самом
  существовании `dd.merge_asof`.

Выбранный минимальный план:

1. Не уходить сразу в ручной `searchsorted`.
2. Добавить диагностические `DASK_DATAFRAME_STATE` после:
   - `merge_asof`;
   - `drop` перед `groupby`;
   - `groupby.agg`;
   - второго `merge` с learning intervals.
3. Добавить `tolerance` в `dd.merge_asof`.
4. Не хардкодить `300`: брать окно из `settings.price_peaks.line_time_duration_min`.

Контракт временного окна:

- BTC price rows строятся через
  `settings.price_peaks.line_time_duration_min`;
- при текущем значении `10` минут:
  - длительность строки = `600` seconds;
  - asof/interval matching half-window = `300` seconds;
- `merge_asof(..., direction="nearest", tolerance=half_window)` должен
  привязывать транзакцию только к ближайшей строке внутри ожидаемого окна, а не
  к далекой метке.

Если после этого run снова упадет:

- смотреть последнюю успешную `DASK_DATAFRAME_STATE` перед ошибкой;
- если падает именно downstream graph optimization, следующий вариант -
  parquet checkpoint после `merge_asof`;
- `searchsorted/map_partitions` остается fallback, а не первый выбор.

### New chat handoff - cost-control

Use this section as the startup context for the next chat.

```text
Проект: I:\projects\trade_app_project.
Активная итерация: 14 - Main ML pipeline correctness.
Работаем в cost-control mode:
- без broad audit без подтверждения;
- не читать большие логи целиком;
- web только если локального контекста недостаточно;
- перед крупной правкой дать короткий plan/logic trace.

Обязательно прочитать:
- AGENTS.md;
- docs/active_work_plan.md;
- docs/iterations/iteration_14.md;
- docs/codex_cost_control.md.

Restore point:
- commit/tag: cad3a11 / restore/iteration-14-start.

Текущий технический фокус:
- получить хотя бы один успешный main-pipeline/smoke после обновления
  зависимостей;
- текущий known failure после run 141:
  'MergeAsof' object has no attribute 'how';
- перед этим run 141 успешно прошел correlation chunk processing:
  successful_chunks=237 total_chunks=237.

Последняя выбранная правка:
- оставить dd.merge_asof;
- добавить tolerance из settings.price_peaks.line_time_duration_min;
- добавить DASK_DATAFRAME_STATE checkpoints после merge_asof/groupby/merge.

Не трогать без отдельного согласования:
- SQLite maintenance, indexes, bulk data mutations;
- parser runtime behavior;
- большой redesign collector/wallet_stats до успешного текущего pipeline run.

Следующий узкий шаг:
- запустить narrow tests вокруг data_operations/time-window contract;
- затем выполнить короткий smoke или full main-pipeline run и смотреть только
  новые строки лога по run_id.
```

## Definition of Done

- Train и predict используют один и тот же preprocessing contract.
- `index` не попадает в model features случайно.
- Timestamp range filters имеют корректные parentheses.
- `threshold` / `decision_threshold` приведены к понятному контракту.
- Feature schema mismatch ловится явно.
- Добавлены focused tests или documented smoke checks.
- Старые profit-test/model результаты помечены как legacy/unverified, если они
  были получены до исправления контрактов.
- README impact check выполнен перед закрытием итерации.

## Industry note (de-facto alternatives)

- Выбранный подход в итерации: minimal correctness patch вокруг существующего
  pipeline.
- Альтернатива (de-facto): полноценный sklearn artifact contract через
  `Pipeline` + сохраненный feature schema + model metadata.
- Почему не берем сейчас: цель итерации - быстро убрать известные источники
  ложных результатов без большого redesign.
- Мини-пример:

```python
model = Pipeline([
    ("scaler", StandardScaler()),
    ("regressor", ElasticNet()),
])
model.fit(train_features[feature_columns], target)
```
