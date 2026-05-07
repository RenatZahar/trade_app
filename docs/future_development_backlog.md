# Future Development Backlog

## Тема

Следующие ходы развития проекта после технической шлифовки

## Статус

Backlog

## Когда делать

После технической шлифовки проекта и стабилизации основного runtime/test-контура.

## Почему это не iteration-файл

Этот документ раньше жил как `docs/iterations/iteration_13.md`, но по смыслу
оказался не закрываемой итерацией, а большим планом будущего развития.

Чтобы не конфликтовать с `docs/active_work_plan.md` и не занимать номер
следующей рабочей итерации, он вынесен из `docs/iterations/` без потери
содержимого.

## Контекст

- В проекте есть старый рабочий flow в Jupyter notebook, который пока не адаптирован к текущему application runtime.
- Понадобится отдельный сценарий проверки, что текущий пайплайн приложения совпадает со старым flow на одинаковых входных данных.
- Прямого доступа к notebook-логике из текущего runtime пока нет, поэтому задача откладывается как оформленный техдолг, а не реализуется частично.
- Для задач с большими SQLite-таблицами и maintenance-сценариями действует правило из `docs/maintenance_guidelines.md`: сначала design review альтернатив, затем реализация выбранного варианта.

## Цель итерации

Зафиксировать и структурировать следующие направления развития проекта так, чтобы после стабилизации runtime/test-контура их можно было брать в работу как отдельные инженерные задачи, а не как набор разрозненных идей.

## Что понадобится сделать

- Закрыть оформленные ниже технические долги итерации.
- Договориться о воспроизводимом формате артефактов и способе локализации расхождений между шагами пайплайна.
- Перед задачами, которые затрагивают массовые пересчеты или bulk-update БД, отдельно оценивать full scan, `GROUP BY`, индексы, возможность остановки и продолжения.

## Технические долги итерации

### 0.1 Разобрать временный Windows startup workaround для `pandas`

Контекст:

- Во время запуска обычного parser run процесс вставал сразу после
  `run_started` / `run_metadata` и не доходил до `Runtime preflight passed`.
- Диагностика показала, что зависание происходило не в Bitcoin Core RPC и не в
  SQLite, а раньше: при импорте `pandas`.
- `faulthandler` показал стек внутри стандартного Python:
  `pandas.compat._constants -> platform.machine() -> platform.uname() ->
  platform.win32_ver() -> platform._wmi_query`.
- На этой Windows-сессии WMI/CIM-запрос зависал. Из-за этого любой модуль,
  который импортировал `pandas` до runtime-кода приложения, мог остановить
  старт сценария до preflight, логирования профиля parser runtime и managed
  restart Bitcoin Core.

Что было сделано как временный обход:

- добавлен проектный `sitecustomize.py`;
- в нем для Windows заранее заполняется `platform._uname_cache` из безопасных
  переменных окружения `PROCESSOR_ARCHITEW6432` /
  `PROCESSOR_ARCHITECTURE` и `COMPUTERNAME`;
- `sitecustomize` явно импортируется до `pandas` в parser/runtime и других
  модулях, где `pandas` импортируется на верхнем уровне;
- цель правки - не менять бизнес-логику, а не дать Windows WMI зависнуть до
  старта сценария.

Почему это техдолг:

- `platform._uname_cache` - приватная деталь стандартной библиотеки Python, а
  не публичный API;
- причина может быть внешней к проекту: сломанный/зависший WMI/CIM, состояние
  Windows Management Instrumentation service, конкретная версия Python,
  `pandas` или окружения;
- если WMI/CIM починить или обновить dependency stack, workaround может стать
  лишним;
- явные `import sitecustomize  # noqa: F401` перед `pandas` выглядят
  неочевидно без этого контекста.

Задача:

- воспроизвести проблему на чистом старте Windows/venv:
  `.venv\Scripts\python.exe -X faulthandler -c "import pandas"`;
- отдельно проверить:
  `.venv\Scripts\python.exe -X faulthandler -c "import platform; print(platform.machine())"`;
- проверить состояние WMI/CIM вне Python:
  `Get-CimInstance -ClassName Win32_OperatingSystem`;
- понять, проблема системная или связана с конкретными версиями
  `Python 3.12.2`, `pandas 3.0.2`, `numpy 2.4.4`;
- если `platform.machine()` и `import pandas` стабильно завершаются без
  зависания, попробовать удалить `sitecustomize.py` и явные импорты
  `sitecustomize`, затем прогнать smoke-тесты и parser startup check;
- если workaround остается, оформить его как осознанный Windows compatibility
  layer с тестом/комментарием около единственной точки подключения.

Критерий удаления:

- `import pandas`, `import runtime_scenarios`,
  `python main.py --help` и parser startup до `Runtime preflight passed`
  стабильно проходят без `sitecustomize`;
- `platform.machine()` не зависает в течение 5-10 секунд;
- нет новых зависших `python.exe` процессов после проверки.

### 1. Сравнение current pipeline и legacy notebook pipeline

- Адаптировать legacy-логику из Jupyter notebook к application runtime.
- Написать сценарий сравнения `current app pipeline` vs `legacy notebook pipeline`.
- Разобрать `tests.ipynb` и решить, какие идеи из notebook еще актуальны после текущих изменений проекта:
  - что переносить в `integration_live`;
  - что переносить в debug-docs или `scripts/debug`;
  - что удалить как устаревший exploratory-код.
- Разобрать `scripts/debug/converge_of_elasticnet.py`:
  - либо встроить идею проверки intermediate parquet artifacts в новый artifact-based diff;
  - либо удалить сценарий как устаревший debug-код.
- Вероятно, добавить декоратор или близкий instrumentation-layer, который будет:
  - сохранять результаты ключевых функций в файлы;
  - делать это одинаково для основного и legacy/test пайплайна;
  - позволять сравнивать промежуточные шаги, а не только финальный результат.
- Зафиксировать единый формат артефактов:
  - parquet / csv / json summary;
  - имя шага;
  - входные параметры;
  - контрольный run id или seed;
  - понятный путь хранения для последующего diff.
- Обратить внимание на пункт 4 из этой итерации - может ли он влиять на результаты теста

Ожидаемый артефакт итерации:
- Отдельный тест/сценарий сравнения двух пайплайнов.
- Набор промежуточных файлов-артефактов по ключевым шагам.
- Документированный diff-процесс: где смотреть расхождения и как локализовать шаг, на котором пайплайны разошлись.

### 1.1 Agentic stop/resume contract после переделки data-flow

После переделки способа сбора данных для `main-pipeline` отдельно вернуться к
stop/resume и idempotency contract:

- определить, какие шаги `main-pipeline` можно безопасно повторять;
- определить, какие шаги должны переиспользовать готовые artifacts;
- зафиксировать, когда нужен новый `run_id`, а когда допустимо продолжение
  существующего logical run;
- описать, что происходит при остановке после каждого дорогого шага:
  data collection, feature/correlation data, clean data, train, evaluate,
  save model;
- связать этот контракт с `logs/agent_runs/<run_id>/manifest.json`,
  `events.jsonl` и `summary.json`;
- не реализовывать полноценный resume до стабилизации data collection/artifact
  layer.

Отдельно, более низким приоритетом, проработать stop/resume для `param-grid`:

- решить, какие parquet artifacts являются валидным cache;
- определить, как проверять соответствие cache текущим grid params/time params;
- описать поведение при остановке worker-пула;
- решить, нужен ли resume отдельных grid combinations или достаточно
  безопасного повторного запуска всего сценария.

### 1.2 Проверка и оптимизация `param-grid`

Цель:

- проверить, что сценарий `python main.py param-grid` работает после
  стабилизации `main-pipeline`;
- разделить параметры, которые меняют математику модели, и performance knobs,
  которые должны менять только скорость;
- определить, какие промежуточные parquet artifacts можно кэшировать, чтобы не
  пересчитывать дорогую correlation/data-collection часть для каждой
  комбинации.

Поведенческие параметры, которые нужно явно поддержать в grid/contract:

- Price/peaks layer:
  - `settings.price_peaks.line_time_duration_min`:
    размер ценовой свечи/сглаженного ряда в минутах; сейчас `10`;
  - `PRICE_LINE_DURATION_SEC = line_time_duration_min * 60`;
  - `PRICE_LINE_HALF_WINDOW_SEC = PRICE_LINE_DURATION_SEC / 2`;
  - `merge_asof(..., tolerance=PRICE_LINE_HALF_WINDOW_SEC)`, то есть tolerance
    задается в секундах и является производной от `line_time_duration_min`;
  - buy/sell interval flags в tx features задаются вокруг `Buy`/`Sell`
    timestamps из peaks-data: `tmsp ± PRICE_LINE_HALF_WINDOW_SEC`;
  - `settings.price_peaks.cicle`: используется как минимальная дистанция между
    peaks в днях через `distance = cicle * 24 * 60 / line_time_duration_min`;
  - `settings.price_peaks.price_diff_pct`: минимальная разница цены в процентах
    для отбора движения;
  - `settings.price_peaks.plato`: процентная ширина ценового плато вокруг
    min/max цены, где помечаются дополнительные buy/sell points;
  - hardcoded детали `price_peaks_func.py` (`width=1`, сдвиги индексов,
    `end_peak+10`, правила `identify_trade_intervals`) пока не включать в grid,
    но зафиксировать как часть текущего label-generation contract.
- Model params:
  - `model.model_param.alpha`;
  - `model.model_param.l1_ratio`;
  - `model.model_param.decision_threshold`.
- Time params:
  - `iterations`;
  - `training_data_duration_months` / future `training_data_duration_days`;
  - `profit_test_months` / future `profit_test_days`;
  - `model_relevance_period_months` / future `model_relevance_period_days`;
  - `time_to_get_cmlt_day`;
  - hardcoded month length `30 * 24 * 60 * 60` не трогать в первом grid audit,
    но явно записывать в metadata.
- Data/wallet filters:
  - `filters.txs_count_of_wallets`;
  - `filters.correlation_threshold`;
  - `settings.data_operations.TOTAL_AMOUNT_MORE_THAN_BTC`;
  - recency filter в `filter_txs_of_chunk`: если train window достаточно
    большой, wallet должен иметь последний tx во второй половине train window;
  - `correlation_type`: `basic` / `optimized`.
- Feature decay:
  - `time_frame_hours = 6`;
  - `tau = time_frame_hours * 6`;
  - `alpha = 1 - exp(-1 / tau)`;
  - сейчас это hardcoded feature-engineering behavior; решить, включать ли
    `time_frame_hours` в grid после проверки базового `param-grid`.

Параметры, которые уже лежат в `grid_params`:

- `model_param`;
- `time_params`;
- `correlation_params`;
- `filters`.

Параметры, которые пока не лежат в `grid_params`, но могут менять итог модели:

- `settings.price_peaks.*`;
- `settings.data_operations.TOTAL_AMOUNT_MORE_THAN_BTC`;
- hardcoded feature-decay `time_frame_hours`;
- hardcoded peak-label rules.

Seed contract:

- для полного `param-grid` без sampling и при текущем `ElasticNet` seed не
  должен менять результат;
- seed нужен для `--test-fraction`, потому что он выбирает подмножество grid /
  data;
- seed нужно сохранить в metadata и cache-key, чтобы test-fraction artifacts
  были воспроизводимы;
- если появятся stochastic models или stochastic training режимы, seed должен
  прокидываться в model params.

Artifact/cache contract для ускорения:

- cache-key должен включать все параметры, которые меняют входные данные или
  признаки:
  price/peaks settings, time windows, filters, `correlation_type`,
  `TOTAL_AMOUNT_MORE_THAN_BTC`, feature-decay settings, DB identity/range,
  `line_time_duration_min`, seed/test-fraction при sampling;
- cache-key не должен включать только model-only параметры (`alpha`,
  `l1_ratio`, `decision_threshold`), если cached train/profit DataFrames уже
  построены и feature columns совпадают;
- перед использованием `PARAM_GRID_RESULTS` проверять timestamp range,
  feature schema, label/action distribution, source DB range и настройки
  generation contract, а не просто наличие parquet файлов.

Performance knobs, которые не должны менять математику и не являются частью
param search:

- Dask worker/thread/memory profile;
- `MAIN_PIPELINE_CORRELATION_CHUNK_SIZE` и param-grid chunk size;
- Dask temp dir / shuffle / spill настройки;
- parquet checkpoint placement, если он behavior-preserving.

### 2. Проверка расхождений в data consistency test вокруг `Btc_block_time_price`

- Прогнать live-тест на соответствие SQL-данных и повторной BTC-реконструкции.
- Подтвердить или опровергнуть гипотезу, что оставшееся массовое расхождение вызывается именно полем `Btc_block_time_price`, а не blockchain-данными как таковыми.
- После подтверждения гипотезы отдельно решить, нужен ли сервисный сценарий, который заново пересчитает и перезапишет `Btc_block_time_price` по всей обучающей БД.
- Если такой сценарий потребуется:
  - зафиксировать источник истинного price lookup;
  - определить формат безопасного bulk-update;
  - решить, должен ли пересчет обновлять `data_table` напрямую или собирать новую производную БД/таблицу.

### 3. Найти способ объединять кошельки по акторам

- Исследовать, можно ли и как корректно объединять несколько `Wallet_id` в более высокий уровень сущности `actor`.
- Определить признаки для такого объединения:
  - on-chain связи;
  - поведенческие паттерны;
  - устойчивые эвристики против ложных склеек.
- Определить, на каком этапе пайплайна actor-level агрегация должна появляться:
  - при подготовке данных;
  - как отдельный enrichment;
  - как downstream-производная таблица.
- Зафиксировать ограничения и риски:
  - ложное объединение независимых кошельков;
  - потеря полезной детализации;
  - смещение корреляционных и обучающих признаков.

### 4. Проверить места, где `Transaction_id` мог ошибочно считаться уникальным

- В проекте могла существовать логика, где `Transaction_id` неявно воспринимался как уникальный ключ строки.
- Для сравнения старого и нового пайплайна это нужно явно перепроверить:
  - в текущей модели одному `Transaction_id` соответствуют разные строки;
  - различия возможны как минимум по `Wallet_id`, `n`, знаку и величине `Amount`;
  - значит любые промежуточные сравнения и сохранение артефактов должны учитывать это на уровне схемы данных.

### 5. SQL performance review для пайплайна обучения моделей

Учебная цель: отдельно разобрать SQL-таблицы, индексы и производительность на
примере текущего проекта. Этот блок перенесен из `iteration_05`, потому что
пятая итерация была про тестовый фундамент, а глубокая SQL-тема относится к
следующим направлениям развития.

- Повторить теорию по индексам:
  - что такое индекс физически и логически;
  - чем обычный индекс отличается от составного;
  - почему порядок колонок в составном индексе критичен;
  - как индексы ускоряют `WHERE`, `JOIN`, `ORDER BY`;
  - почему индексы замедляют `INSERT`, `DELETE`, `UPDATE`;
  - чем отличаются рабочие индексы pipeline от maintenance-индексов.
- Разобрать "связанные индексы" в контексте SQLite:
  - в SQLite индекс всегда относится к одной таблице, а не к нескольким таблицам
    сразу;
  - "связанный индекс" в нашем разговоре означает индекс, созданный для
    конкретной таблицы, например `idx_service_wallet_move_plan_batch` для
    `service_wallet_move_plan`;
  - если удалить таблицу через `DROP TABLE`, SQLite удаляет и индексы этой
    таблицы, потому что без таблицы они не имеют смысла;
  - индексы разных таблиц могут участвовать в одном `JOIN`, но каждый из них
    все равно обслуживает свою таблицу.
- Разобрать другие краеугольные камни SQL:
  - модель данных: таблицы, ключи, нормализация и денормализация;
  - форма запроса: почему два похожих запроса могут иметь разную стоимость;
  - дорогие операции: `ORDER BY`, `GROUP BY`, `DISTINCT`, вложенные сканы;
  - join strategy: как соединяются таблицы и почему плохой `JOIN` ломает производительность;
  - транзакции: размер батча, цена `COMMIT`, цена rollback;
  - I/O и WAL: диск, WAL, checkpoint, synchronous, размер батчей;
  - статистика планировщика: зачем нужен `ANALYZE`;
  - кардинальность данных: почему индекс по колонке с 2 значениями слабее индекса по высокоразличимой колонке;
  - физический объем данных: почему на сотнях миллионов строк магии нет даже с хорошими индексами.
- Привязать теорию к проекту:
  - почему `idx_wallet_id` полезен для `move_txs`;
  - почему `idx_block_height` и `idx_txs_blocktime` полезны для рабочих сценариев, но вредны во время массового переноса;
  - почему `service_wallet_move_plan` требует отдельного индекса под выбор батча;
  - почему индекс, который ускоряет анализ, может тормозить maintenance-сценарий.

Главная мысль для закрепления: индексы нужны не "вообще", а под конкретный
запрос и конкретную фазу пайплайна.

- Проверить, по каким индексам сейчас идет сбор данных в пайплайне обучения моделей:
  - зафиксировать фактически используемые индексы на ключевых SQL-этапах подготовки train-data;
  - отдельно отметить, какие индексы реально используются планировщиком через `EXPLAIN QUERY PLAN`, а какие нет.
- Изучить возможность создания индексов под пайплайн:
  - проверить составной индекс `idx_block_height_wallet_id` для запроса `WHERE Block_height IN (...) GROUP BY Wallet_id`;
  - сформировать дополнительные гипотезы по составным индексам для частых `WHERE`, `JOIN`, `ORDER BY`;
  - оценить компромисс между ускорением чтения и ценой на вставку/обновление данных.
- Проверить, существует ли в текущем стеке режим "отсортированной таблицы" и можно ли его применить:
  - зафиксировать поддерживаемые механизмы SQLite и альтернативных форматов хранения;
  - дать вывод, применимо ли это к текущей схеме и ограничениям пайплайна.
- После массовых maintenance-операций отдельно оценить необходимость `ANALYZE`.


### 6. Пересмотреть модель `data_table` + `few_tx_wallets`

- Текущая модель `data_table` + `few_tx_wallets` физически разносит одинаковые транзакционные строки по двум таблицам.
- Эта модель может ускорять рабочие выборки ценой очень дорогого maintenance-переноса строк.
- Отдельно принять решение по `data/block_height_block_time_map/map.parquet`:
  - сейчас это локальный parquet-cache соответствия `block_heights` ->
    `block_times`;
  - он используется legacy `data_operations.py` для перевода timestamp-окон в
    диапазоны блоков и ускорения выборок вокруг price/peak intervals;
  - при переходе к модели `data_table` + `wallet_stats` / статистическим
    таблицам по кошелькам нужно решить, остается ли карта отдельным parquet
    cache, переносится ли в SQLite/service-таблицу, пересчитывается ли из
    `data_table`, или заменяется другим lookup-слоем;
  - нужно зафиксировать source of truth для `Block_height` -> `Block_time`,
    правила обновления после загрузки новых блоков и проверки покрытия диапазона.
- Рассмотреть альтернативу:
  - `data_table` хранит все строки транзакций;
  - `wallet_stats` хранит `Wallet_id`, общее количество строк/транзакций, признаки активности и флаги вроде `is_low_tx`;
  - рабочий pipeline фильтрует строки через `JOIN` или `EXISTS`, а не через физический перенос строк.
- Рассмотреть добавление явного boolean-флага в `wallet_stats`, например
  `is_ready_for_training` / `is_low_tx` / `is_dirty`, чтобы pipeline мог
  быстро отличать уже обработанные кошельки от тех, которые требуют пересчета.
- Спроектировать инкрементальный пересчет вместо пересчета всей `data_table`:
  - после загрузки новых блоков фиксировать только затронутые `Wallet_id`;
  - пересчитывать статистику только по кошелькам, которые появились в новом
    скачанном диапазоне данных;
  - не запускать полный `GROUP BY Wallet_id` по всей БД без отдельного design
    review.
- Хранить список требующих обработки кошельков/диапазонов в отдельной
  service-таблице, например `wallet_stats_rebuild_queue`:
  - `Wallet_id`;
  - диапазон блоков или timestamp-окно, из-за которого кошелек попал в очередь;
  - статус обработки (`pending`, `processing`, `done`, `error`);
  - счетчик попыток и время последней ошибки;
  - batch/run id, чтобы процесс можно было безопасно остановить и продолжить.
- Проверить идемпотентность такого процесса:
  - повторный запуск не должен дублировать работу;
  - частично обработанный batch должен либо докатываться, либо переигрываться
    предсказуемо;
  - очередь должна позволять понять, что уже обработано, а что осталось.
- Отдельно учесть двухуровневую фильтрацию:
  - глобальный фильтр кошельков по всему доступному периоду данных;
  - локальный фильтр кошельков внутри обучающего окна, например за год.
- Проверить, ускорит ли такая модель подготовку данных без потери текущей семантики фильтров.

Дополнительный вопрос: имеет ли смысл создавать таблицу не только со сводными данными по кошелькам, но и держать там список tmps где есть их транзакции?

При добавлении новых SQLite-таблиц нужно не полагаться на память, а обновлять
явный DB schema contract:

- новая таблица добавляется в контракт схемы;
- сценарии, которым нужна таблица, указывают свою зависимость от нее;
- smoke-тест проверяет, что все runtime DB-зависимости покрыты контрактом;
- live DB smoke-проверка warning-only подсвечивает таблицы, которые есть в БД,
  но еще не описаны в контракте;
- если таблица экспериментальная, legacy или service-only, это должно быть
  явно отражено решением, а не оставаться неявным drift между БД и кодом.

Текущее состояние после follow-up к `iteration_08`:

- добавлен начальный DB schema contract для `data_table`;
- smoke-тесты проверяют, что runtime-сценарии с `blocks_sql_data` покрыты
  зависимостями таблиц, а зависимости таблиц описаны в DB contract;
- live DB smoke-проверка warning-only подсвечивает таблицы, которые есть в БД,
  но не описаны в DB contract;
- локальная legacy-таблица `few_tx_wallets` была проверена через
  `SELECT 1 FROM few_tx_wallets LIMIT 1`, оказалась пустой и была удалена через
  `DROP TABLE few_tx_wallets` без `VACUUM`;
- итоговый smoke после удаления: `56 passed, 1 warning`; warning по
  `few_tx_wallets` исчез, остался только pandas deprecation warning в
  `data_operations.py`.

### 7. Аудит старых сценариев запуска из `main.py`

После `iteration_06` и `iteration_07` `main.py` сильно очищен. На текущий
момент в рабочем entrypoint осталось 4 сценария:

- `main-pipeline` - price updater + подготовка peaks + обучение новой модели;
- `param-grid` - подбор параметров модели;
- `--start_parser` - запуск BTC/parser monitor flow;
- `test downloaded-from-btc-data` - integration-live проверка SQL/BTC
  consistency.

В старых версиях `main.py` существовало больше сценариев и debug/test-веток.
При отдельном разборе старых сценариев нужно пройтись по ним и для каждого принять решение:
вернуть как нормальный CLI/runtime сценарий, перенести в `scripts/debug` /
`integration_live`, или окончательно удалить как устаревший код.

Исторические сценарии:

- default startup самого раннего `main.py`: price updater + BTC core monitor +
  blockchain parser + sleep-loop;
- `--start_parser` / `run_parser` - запуск blockchain parser flow;
- `flask` / `FLASK_TEST` - запуск только Flask;
- `main_pipeline` / `MAIN_TEST` - старый тестовый запуск Flask + updater +
  peaks + training с `TEACHING_TEST=1`;
- `param_grid` / `PARAM_GRID_TESTING` - старый тестовый запуск param-grid;
- `converge_elasticnet` / `TESTS_FROM_MODULES` - debug-проверка сходимости
  ElasticNet;
- `right_now_test` - запуск parser "прямо сейчас" через
  `run_parser_now_and_wait`;
- `test downloaded-from-btc-data` - integration-live data consistency test;
- `move_txs` - legacy physical split `data_table -> few_tx_wallets`;
- `return_few_tx_wallets` - старый частичный возврат `few_tx_wallets ->
  data_table`;
- `move_txs_back` - финальный возврат всех строк в `data_table` с cleanup /
  indexes / optional `VACUUM` / `ANALYZE`.

Предварительное решение по известным пунктам:

- `move_txs`, `return_few_tx_wallets`, `move_txs_back` не возвращать в рабочий
  CLI: physical split признан слабо жизнеспособным подходом и архивирован в
  `docs/experiments/moving_txs_physical_split/`;
- `test downloaded-from-btc-data` оставить как integration-live сценарий, но
  держать отдельно от обычного unit/smoke контура;
- `converge_elasticnet` и `right_now_test` проверить на актуальность: если они
  нужны, оформить как debug/integration scripts с явными входами и expected
  output; если нет - удалить;
- `flask`, старый `main_pipeline` и старый `param_grid` сравнить с текущими
  `main-pipeline` / `param-grid` и не возвращать дубли, если поведение уже
  покрыто текущими командами;
- отдельно решить статус текущего `main-pipeline`: это постоянный production
  process или исследовательская заготовка для обучения новой модели. Сейчас
  временные окна берутся из `model.time_params`, а не из аргументов команды.

Ожидаемый артефакт:

- таблица решений по каждому старому сценарию: `keep`, `restore`, `move to
  debug`, `move to integration_live`, `delete`;
- ссылки на фактические файлы/коммиты, где сценарий жил;
- обновленный README/CLI help, где перечислены только поддерживаемые сценарии.

### 8. Ревизия technical debt comments из `runtime_scenarios.py`

Во время `iteration_07` `main_functions.py` переименован в
`runtime_scenarios.py`, и из рабочего файла убраны старые
закомментированные заметки. Их нужно не терять, а проверить в будущей
технической итерации: какие еще актуальны, какие стоит оформить задачами, а
какие удалить окончательно как устаревшие.

Перенесенные вопросы:

- Parser restart after error:
  - старый комментарий: в некоторых случаях parser отправляет
    `send_message('parser_status', 'completed with error')`;
  - source context: исходная заметка была в pre-rename
    `main_functions.py:33-35`, текущее место поведения -
    [parser_runtime.py](I:/projects/trade_app_project/modules/blockchain_parser/parser_runtime.py:89);
  - не был реализован перезапуск parser после этого сообщения с задержкой;
  - нужно решить, нужен ли auto-restart parser flow, или достаточно текущего
    fail-fast/logging поведения.
- `parser_status` listener:
  - старый commented-out код:
    `waiting_for_message('parser_status', start_blockchain_parser)`;
  - source context: исходная заметка была в pre-rename
    `main_functions.py:38`, текущий active listener -
    [parser_runtime.py](I:/projects/trade_app_project/modules/blockchain_parser/parser_runtime.py:39);
  - нужно решить, должен ли parser lifecycle слушать отдельный status-channel
    или текущий `check_btc_core_status_line` достаточен.
- Thread lifecycle policy:
  - старая заметка: daemon-потоки завершаются вместе с программой, non-daemon
    потоки заставляют программу дождаться завершения;
  - source context: исходная заметка была в pre-rename
    `main_functions.py:39-41`, текущие daemon-потоки - BTC monitor
    [parser_runtime.py](I:/projects/trade_app_project/modules/blockchain_parser/parser_runtime.py:41)
    и Flask [flask_runtime.py](I:/projects/trade_app_project/modules/flask_module/flask_runtime.py:24);
  - нужно явно описать policy для Flask, BTC monitor, parser и потенциальных
    save/cleanup операций.
- BTC price updater threading:
  - старое решение: `clean_raw_data()` запускался не в отдельном потоке, чтобы
    peaks корректно отработали;
  - рядом был commented-out вариант через daemon thread;
  - source context: исходная заметка была в pre-rename
    `main_functions.py:57-60`, текущий синхронный вызов -
    [runtime_scenarios.py](I:/projects/trade_app_project/runtime_scenarios.py:23),
    wrapper вокруг `clean_raw_data()` -
    [runtime.py](I:/projects/trade_app_project/modules/bts_price_updater/runtime.py:4);
  - нужно решить, должен ли price update оставаться синхронным шагом
    `main-pipeline`, или его можно безопасно вынести в отдельный lifecycle.
- Redis startup shape:
  - старая заметка рядом с `if not start_redis()`: "не нравится конструкция,
    переписать";
  - source context: исходная заметка была в pre-rename
    `main_functions.py:64`, текущий contract функции -
    [parser_runtime.py](I:/projects/trade_app_project/modules/blockchain_parser/parser_runtime.py:24),
    текущий call site - [parser_runtime.py](I:/projects/trade_app_project/modules/blockchain_parser/parser_runtime.py:37);
  - нужно решить, оставить boolean-return contract, заменить на fail-fast
    exception внутри `start_redis()`, или выделить отдельный startup/check
    объект.

Ожидаемый артефакт:

- короткое решение по каждому пункту: `keep as is`, `implement`, `delete`,
  `move to docs`;
- если пункт остается актуальным - отдельная задача с тестируемым критерием;
- если нет - удалить остаточные comments/legacy hooks из кода.

### 9. Repository tooling и структура служебных скриптов

- Принять решение по месту для repo tooling/scripts, включая
  `scripts/update_requirements_lock.py`.
- Варианты решения:
  - оставить отдельную папку `scripts/`, если она станет явно описанной зоной
    repository tooling;
  - перенести такие утилиты в более явную служебную зону проекта;
  - разнести утилиты по владельцам, если они относятся к конкретным подсистемам.
- Зафиксировать правило в README или developer docs, чтобы новые служебные
  скрипты не появлялись в случайных местах.

### 10. Public/private boundary для портфолио-репозитория

- Принять решение, как честно разделять публичную engineering-часть проекта и
  приватную production strategy logic.
- Рассмотреть замену ignored production-файлов вроде `data_operations.py` на
  публичную demo-реализацию или заглушку, например
  `build_training_features(...)` с docstring о том, что production strategy
  lives in private package.
- В README явно описать границу:
  - public repo демонстрирует engineering infrastructure;
  - proprietary strategy logic/data/model artifacts не включены;
  - smoke tests покрывают public runtime contracts.
- Сравнить варианты:
  - demo-заглушка в public repo;
  - private package/core repo;
  - приватный remote для полного проекта;
  - другой формат разделения.

### 11. Постепенное введение lint

- После первого CI gate не включать обязательный lint всего проекта сразу:
  это может поднять большой старый backlog, не связанный с текущей итерацией.
- В технической итерации отдельно решить, какой lint нужен и как вводить его
  постепенно:
  - только измененные файлы;
  - только новые/очищенные модули;
  - warning-only режим;
  - отдельный optional check до перевода в обязательный gate.

### 12. Parser runtime hardening note

- 2026-05-03 parser runtime hardening and live diagnostics are recorded in
  [parser_runtime_hardening_2026-05-03.md](../experiments/parser_runtime_hardening_2026-05-03.md).
- The immediate production decision is `QUANTITY_OF_BLOCKS_IN_ITERATION = 10`.
- Deeper parser/ZMQ/lifecycle work remains future research.

## Почему это отложено

- Сейчас в приоритете техническая стабилизация проекта:
  - CLI;
  - logging/tracker;
  - SQL-state consistency;
  - integration/live tests;
  - приведение data-flow к воспроизводимому состоянию.
- Без этой стабилизации сравнение с notebook рискует превратиться в разовый debug-эксперимент вместо инженерного regression-сценария.


