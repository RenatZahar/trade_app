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
