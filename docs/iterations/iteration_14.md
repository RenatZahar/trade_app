# Iteration 14 - Main ML pipeline correctness

## Тема

Исправление небольших, но критичных вопросов корректности в основном ML
pipeline перед доверием к model/profit-test результатам.

## Статус

Started

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

Порядок работы:

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
