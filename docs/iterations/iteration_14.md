# Iteration 14 - ML pipeline correctness and trading validation

## Тема

Исправление и тестирование ML/trading pipeline после ревизии регрессионной модели.

## Статус

Planned

## Дата старта

2026-05-04

## Контекст

- Текущая идея модели: искать кошельки, которые исторически покупали перед ростом цены или продавали перед падением, агрегировать их сигналы и проверять, повторяется ли сигнал на новых данных.
- Рабочий горизонт сейчас ближе к дням, примерно от недели до двух.
- Предварительные результаты выглядели перспективно: тестовая модель показывала около `17%` за полтора месяца, alpha-версия приложения - около `7%`, но статистики пока мало.
- Ревизия показала, что до оценки торгового edge нужно закрыть несколько инженерных рисков: возможный leakage, несогласованный preprocessing train/predict, спорный target/threshold contract и недостаточно строгий backtest.
- Эта итерация не должна расширять стратегию новыми фичами до тех пор, пока базовый пайплайн не станет воспроизводимым и проверяемым.

## Цель итерации

Сделать pipeline обучения и проверки модели технически корректным, воспроизводимым и пригодным для честной оценки торговой гипотезы.

Главный результат: после итерации должно быть понятно, есть ли у текущего on-chain signal layer устойчивый полезный сигнал, или прежние проценты могли появиться из-за ошибок пайплайна, leakage, несогласованного scaling или слабого backtest-протокола.

## Что входит в scope

### 1. Исправление ML contract

- Проверить и исправить train/predict preprocessing:
  - сейчас обучение использует `StandardScaler().fit_transform(...)`;
  - profit-test может вызывать `model.predict(...)` на raw features;
  - целевой вариант - `sklearn Pipeline(StandardScaler(), ElasticNet())` или сохранение scaler вместе с моделью.
- Убрать случайное попадание `index` в список features, если нет явного доказанного смысла использовать его как признак.
- Зафиксировать feature schema contract:
  - какие колонки входят в модель;
  - какие колонки служебные;
  - что происходит при missing/extra columns.
- Унифицировать `threshold` / `decision_threshold`, чтобы runtime, config и profit-test использовали один контракт.

### 2. Исправление временных фильтров и data alignment

- Проверить фильтры timestamp windows, особенно выражения вида:
  - `Timestamp >= start & Timestamp <= end`;
  - они должны быть явно обернуты в скобки вокруг каждого условия.
- Проверить `merge_asof(..., direction='nearest')`:
  - не размазывает ли он транзакции по слишком широкому временному окну;
  - нужен ли явный tolerance или повторное включение проверки `calculate_in_10_min_period`.
- Проверить, что train/test windows не пересекаются по данным, labels и derived artifacts.

### 3. Проверка target и торговой логики

- Зафиксировать, что именно предсказывает модель:
  - `Action` как {-1, 0, 1};
  - future return;
  - score силы сигнала;
  - или другой target.
- Проверить, подходит ли regression на `Action` под текущую торговую задачу.
- Сравнить с более прямыми постановками:
  - classifier для direction/entry;
  - ranking/score model;
  - regime detector;
  - regression по future return.
- Проверить, что `Predicted_Action` действительно приводит к сделкам, а не к скрытому режиму "все время cash".

### 4. Честный profit-test

- Добавить или зафиксировать базовые сравнения:
  - always cash;
  - buy-and-hold;
  - простой price-only/trend baseline;
  - delayed/random signal baseline, если это дешево реализовать.
- Добавить учет торговых издержек хотя бы в минимальном виде:
  - комиссия;
  - spread/slippage;
  - задержка после появления блока и обновления price data.
- В метриках смотреть не только итоговый PnL:
  - max drawdown;
  - exposure;
  - turnover;
  - trade count;
  - profit factor;
  - стабильность по окнам.

### 5. Walk-forward проверка

- Перейти от 1-3 удачных проверок к более строгому протоколу:
  - минимум 5 окон, лучше 5-10;
  - train window и test window фиксируются в metadata;
  - каждый прогон сохраняет config, commit, диапазоны данных и метрики.
- Результаты считать сильными только если они устойчивы по нескольким рыночным режимам, а не только по одному удобному участку.

### 6. Feature audit и ablation

- Проверить текущие признаки:
  - weighted buy/sell correlations;
  - anti-correlations;
  - `SASI-SABI`, `BABI-BASI`;
  - EWM/CMLTV variants.
- Сделать ablation:
  - без `index`;
  - только raw weighted correlations;
  - только CMLTV/EWM features;
  - без потенциально спорных признаков.
- Проверить стабильность коэффициентов/feature importance между окнами.
- Отдельно решить, нужны ли дополнительные данные:
  - OHLCV как features;
  - volatility regime;
  - funding/open interest/order book;
  - exchange flow/entity-level enrichment.

### 7. Data quality gates для parser -> model

- Убедиться, что model pipeline явно знает ограничения parser data:
  - coinbase transactions фильтруются;
  - no-address prev outputs могут выпадать;
  - outputs ниже `MIN_VALUE_THRESHOLD` не попадают в данные;
  - low-tx block differences должны быть классифицированы, а не просто проигнорированы.
- Связать SQL-vs-BTC consistency test с доверием к обучающим данным.
- Не начинать тяжелые bulk-пересчеты SQLite без отдельного design review по правилам `AGENTS.md`.

## Риски

- Старые результаты `7%` / `17%` могут исчезнуть после исправления scaling, leakage и costs. Это нормальный исход проверки, а не регрессия.
- F1/accuracy могут быть misleading из-за сильного дисбаланса классов `Action`.
- `index` или timestamp могут случайно кодировать время/режим рынка и давать ложное качество.
- Издержки и задержка исполнения могут съесть edge даже при положительном raw signal.
- Улучшение модели до фикса pipeline-контрактов может усилить ошибочную логику вместо реального сигнала.

## Варианты вмешательства

### Minimal patch, рекомендуется первым

- Исправить scaler contract через `Pipeline`.
- Убрать `index` из features.
- Исправить timestamp filter parentheses.
- Унифицировать threshold naming.
- Добавить узкие unit/smoke tests на эти контракты.

Плюсы: быстро снижает риск ложных результатов.  
Минусы: не отвечает полностью на вопрос о торговом edge.

### Medium refactor

- Вынести feature schema, preprocessing, model fit/predict и profit-test в более явные слои.
- Добавить общий отчет по walk-forward windows и baseline metrics.

Плюсы: лучше поддерживать и тестировать.  
Минусы: больше изменений, выше риск затянуть итерацию.

### Research slice

- Не менять production pipeline, а собрать отдельный reproducible experiment runner для проверки гипотезы.

Плюсы: быстро сравнивать идеи.  
Минусы: есть риск получить второй параллельный pipeline и снова расходиться с приложением.

## Выбранный план

Начать с `Minimal patch`, затем запускать контролируемые проверки.

Порядок:

1. Закрыть технические дефекты, которые могут искажать результат.
2. Добавить минимальные тесты на исправленные контракты.
3. Пересчитать текущие known-good сценарии и сравнить с legacy результатами.
4. Добавить baseline comparisons и trading costs.
5. Прогнать walk-forward на нескольких окнах.
6. Только после этого решать, расширять ли feature set и менять постановку модели.

## Definition of Done

- Train/predict используют один и тот же preprocessing contract.
- `index` не попадает в features без явного решения и теста.
- Timestamp filters исправлены и покрыты тестом.
- `threshold` / `decision_threshold` приведены к одному контракту.
- Есть feature schema check для train и predict.
- Profit-test показывает не только итоговый процент, но и drawdown, exposure, turnover, trade count и baseline comparison.
- Хотя бы 5 walk-forward окон пройдены или документально зафиксировано, почему это пока невозможно.
- Старые результаты `7%` / `17%` помечены как legacy/unverified, пока не воспроизведены новым протоколом.
- README impact check выполнен перед закрытием итерации.
- После code changes пройден минимум `python -m pytest tests\unit_smoke -q`, если изменения затрагивают runtime/ML pipeline.

## Out of scope

- Оптимизация blockchain parser runtime.
- Перепроектирование SQLite storage и массовые пересчеты данных.
- Live trading execution, exchange API и order management.
- Entity clustering кошельков, если он требует отдельного research/design review.

## Затронутые файлы-кандидаты

- `main.py`
- `runtime_scenarios.py`
- `modules/teach_and_update_models/model_classes.py`
- `modules/teach_and_update_models/data_operations.py`
- `modules/teach_and_update_models/param_grid.py`
- `modules/finding_price_peaks/price_peaks_func.py`
- `data/models/new_models/*.json`
- `data/models/trained_models/*`
- `tests/unit_smoke/*`
- `docs/experiments/*`

## Industry note (de-facto alternatives)

- Выбранный подход в итерации: сначала исправить ML contract и backtest validity, потом улучшать features.
- Альтернатива (de-facto): сразу строить новый research notebook / experiment runner и искать лучшую модель.
- Почему не берем сейчас: без исправления текущего train/predict contract и leakage-risk новые результаты останутся недостоверными.
- Мини-пример:

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import ElasticNet

model = Pipeline([
    ("scale", StandardScaler()),
    ("regression", ElasticNet()),
])
```

## Связанные будущие вопросы

- Является ли текущая on-chain модель самостоятельной trading strategy или только фильтром режима/силы сигнала.
- Несут ли mining-pool/entity-level действия полезный сигнал, если coinbase как таковой не нужен модели.
- Нужно ли переходить с wallet-level на actor/entity-level aggregation.
- Какие дополнительные market data нужны до следующего серьезного улучшения качества.
