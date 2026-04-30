# Iteration 06 - Determinism and experiment control

## Тема

Детерминизм и контроль эксперимента.

## Junior+ компетенция

Junior+ умеет повторять результаты обучения при одинаковых входах и объяснять,
какие параметры, данные, версия кода и runtime-условия участвовали в запуске.

## Статус

Completed

## Контекст старта

- `iteration_05` закрыла базовый тестовый фундамент и была слита в
  `main_branch`.
- Рабочая ветка шестой итерации:
  `feature/iteration-06-determinism-experiment-control`.
- Быстрый smoke-контур после merge показал 2 падения на импорте
  `dask.dataframe` в `tests/unit_smoke/test_correlation_pipeline_contracts.py`.
  Это нужно разобрать в начале итерации, потому что без зеленого smoke-сигнала
  невозможно надежно фиксировать дальнейшие изменения.
- В проекте уже есть `run_tracker`, runtime-конфиг, logging-контур и pytest.
  Это основа для фиксации метаданных эксперимента.

## Цель итерации

Сделать запуск обучения и диагностических сценариев воспроизводимее:

- зафиксировать random seeds в местах, где обучение или подготовка данных могут
  давать разные результаты;
- сохранять метаданные запуска: commit hash, параметры запуска, ключевые
  настройки модели, версию/состояние данных;
- связать результат обучения с конкретным run_id и артефактами логирования;
- оставить понятный минимальный протокол, как повторить эксперимент;
- вернуть быстрый `unit_smoke`-контур в зеленое состояние.

## Затронутые темы

- reproducible ML experiments;
- random seed и controlled randomness;
- experiment metadata;
- Git commit hash как часть provenance;
- data version / data snapshot metadata;
- smoke tests как quality gate перед merge.

## Короткая теория перед практикой

Детерминизм в ML-проекте не означает, что вся система всегда обязана давать
бит-в-бит одинаковый результат на любой машине. Практический минимум:

- одинаковые входные данные;
- одинаковые параметры;
- одинаковая версия кода;
- зафиксированные seed там, где есть случайность;
- сохраненные метаданные, чтобы запуск можно было объяснить и повторить.

Для текущего проекта это важнее, чем преждевременная оптимизация модели: если
результат обучения меняется, сначала нужно понимать, изменились данные, код,
параметры или случайность.

## Стартовый чеклист

- Проверить текущую ветку:

```powershell
git branch --show-current
```

- Проверить, что ветка `feature/iteration-06-determinism-experiment-control`
  отслеживает `origin/feature/iteration-06-determinism-experiment-control`.
- Проверить чистоту рабочей директории. На старте был известный untracked-хвост:
  файл `"tatus -sb"` после опечатки в терминале. Файл проверен и удален как
  мусорный артефакт терминальной опечатки.
- Зафиксировать текущий быстрый тестовый baseline:

```powershell
python -m pytest tests\unit_smoke -q
```

Примечание по `test downloaded-from-btc-data`: команда вида
`python main.py test downloaded-from-btc-data 3 1` не является тестом всего
пайплайна обучения. Это integration-live проверка SQL/BTC consistency: она
выбирает блоки по seed, реконструирует данные через BTC RPC и сравнивает их с
SQL. Такой тест проверяет не "не упал ли весь pipeline", а согласованность
конкретного live-среза данных.

## Предварительный диагноз

- P0: `unit_smoke` падал на импорте `dask.dataframe`; это ломало быстрый сигнал
  качества после merge.
- P0: обучение и диагностические сценарии не гарантировали повторяемость
  результата через единый seed-контур.
- P0: run metadata недостаточно явно связывала запуск с `git commit`,
  параметрами обучения и состоянием данных.
- P1: параметры эксперимента частично жили в коде и CLI, но не выглядели как
  единый snapshot, пригодный для сравнения запусков.

## Кандидаты на первый срез

- `modules/logger/run_tracker.py` - расширить метаданные запуска.
- `settings/runtime.py` и/или профиль настроек модели - найти место для seed и
  параметров эксперимента.
- `modules/teach_and_update_models/*` - найти точки, где задаются random_state,
  seed и параметры обучения.
- `tests/unit_smoke/test_correlation_pipeline_contracts.py` - вернуть smoke
  baseline в зеленое состояние или изолировать тест от тяжелого импорта.

## Варианты вмешательства

### Minimal patch

- Починить падающий `unit_smoke` без переписывания ML-пайплайна.
- Добавить минимальный `experiment_metadata` в `run_tracker`.
- Зафиксировать commit hash и основные параметры запуска.
- Добавить/уточнить 1-2 unit-smoke теста на сбор метаданных.

Плюсы: быстро, низкий риск, хорошо подходит для учебной итерации.

Минусы: не решает полностью архитектуру хранения экспериментов.

### Medium refactor

- Выделить отдельный слой `experiment_context` или аналогичный helper.
- Собрать seed, commit hash, runtime params, model params и data snapshot в одну
  структуру.
- Подключить эту структуру к обучению и логированию.

Плюсы: лучше масштабируется на будущие эксперименты.

Минусы: выше риск затронуть orchestration и тесты шире, чем нужно.

### Rewrite slice

- Локально переписать запуск обучения вокруг явного experiment object:
  config -> data snapshot -> train -> metrics -> artifacts.

Плюсы: самый чистый долгосрочный дизайн.

Минусы: слишком большой объем для текущего состояния; лучше вернуться после
итерации 7 про границы ответственности модулей.

## Рекомендация на старт

Начать с `Minimal patch`.

Причина: после merge уже есть падающий smoke-контур, а шестая итерация должна
сначала восстановить быстрый сигнал качества и добавить минимальную
воспроизводимость. Более крупный experiment-layer логичнее проектировать после
итерации 7, когда будут яснее границы orchestration, бизнес-логики и I/O.

## Принятый практический план

Ускоренный срез `iteration_06`:

- убрать legacy test-ветки основного pipeline из `main.py`;
- не добавлять в CLI новый "тест всего пайплайна";
- оставить `main-pipeline` как обычную runtime-команду без `--seed`, пока в
  ней нет явного тестового среза;
- использовать seed только в сценариях, где действительно есть controlled
  sampling: integration-live test и `param-grid --test-fraction`;
- проверять pipeline-slices через `pytest` с импортом функций и маленькими
  controlled inputs;
- вынести deterministic sampling в маленький helper;
- заменить прямые `random.sample(...)` на sampling с локальным
  `random.Random(seed)`;
- добавить минимальный experiment metadata collector;
- передавать metadata в `RunTracker`;
- логировать metadata один раз на старте run;
- добавить 2-4 быстрых теста на повторяемость, metadata и tracker contract.

За рамками этого среза:

- full end-to-end тест обучения модели;
- подробные type hints для всего data pipeline;
- artifact-based сравнение всего pipeline;
- полный слой DataFrame schema contracts.

Эти задачи остаются для итерации 7 и будущей `iteration_13`.

## Границы итерации

В этой итерации не делаем:

- полную переработку ML orchestration;
- полноценный experiment tracking сервис;
- сравнение current pipeline со старым notebook-flow;
- actor-level объединение кошельков.

Эти задачи остаются будущими итерациями или отдельными design review.

## Definition of Done

- [x] `python -m pytest tests\unit_smoke -q` проходит.
- [x] Понятно зафиксирована причина падения `dask.dataframe` smoke-тестов или
  внесен минимальный фикс.
- [x] В run metadata сохраняется `git commit hash` текущего запуска.
- [x] В run metadata или рядом с ней сохраняются ключевые параметры
  эксперимента.
- [x] Seed/`random_state` явно задан в критичных местах обучения, где это
  применимо.
- [x] Есть минимальный тест или smoke-проверка, подтверждающая сбор metadata.
- [x] В документе итерации зафиксированы выбранный вариант вмешательства,
  результат и ограничения.

## Результат итерации

Выбранный вариант: `Minimal patch`.

Что сделано:

- `main.py` очищен от аргпарса, runtime bootstrap и лишней tracker-обвязки;
- CLI вынесен в `cli_args.py`;
- старт/завершение runtime вынесены в `modules/logger/runtime_bootstrap.py`;
- stage tracking упрощен через `with tracked_stage(...)`;
- `RunTracker` расширен metadata;
- добавлен сбор experiment metadata:
  - `commit_hash`;
  - `seed`;
  - CLI args;
  - версии Python, pandas, dask, scikit-learn;
  - runtime paths/config;
  - SQL state;
  - DB path;
  - model params snapshot;
  - param-grid summary;
- metadata логируется на старте run и обновляется после чтения model/grid
  параметров;
- deterministic sampling вынесен в отдельный helper;
- controlled seed применяется к:
  - integration-live BTC/SQL block sampling;
  - param-grid sampling;
  - data sampling в correlation pipeline;
  - `ElasticNet.random_state`, если seed передан и `random_state` не задан явно;
- legacy `return_few_tx_wallets` сценарий убран из CLI;
- `main-pipeline` оставлен обычной runtime-командой без `--seed`;
- `param-grid` получил `--seed` и `--test-fraction`;
- добавлены unit-smoke тесты на determinism, metadata, runtime bootstrap,
  tracker metadata и CLI contracts.
- проведена исследовательская работа по Codex `AGENTS.md`, skills и
  workflow-дисциплине агента;
- сырой материал по agents/skills систематизирован в два документа:
  - `docs/AGENTS_demo.md` - будущий рабочий протокол агента для проекта;
  - `docs/agents_skills_demo.md` - исследовательская записка по `AGENTS.md`,
    skills, subagents, MCP, GSD/Superpowers/OpenSpec/meta-skill и плану
    внедрения;
- зафиксирован практический вывод: начинать с короткого корневого `AGENTS.md`,
  затем добавить 2-3 repo-scoped skills, а meta-skill использовать только как
  ручную ретроспективу с подтверждением пользователя.

Финальный быстрый тестовый сигнал:

```powershell
python -m pytest tests\unit_smoke -q
```

Результат на 2026-04-30: `41 passed, 1 warning`.

Оставшееся предупреждение: `DeprecationWarning` от pandas
`DataFrameGroupBy.apply` в `modules/teach_and_update_models/data_operations.py`.
Это не блокирует итерацию и должно быть разобрано отдельно.

## Industry note (de-facto alternatives)

- Выбранный подход в итерации: минимальный experiment metadata поверх текущего
  `run_tracker`.
- Альтернатива (de-facto): отдельный experiment tracker, например MLflow или
  Weights & Biases.
- Почему не берем сейчас: внешний tracking-tool преждевременен, пока проект еще
  стабилизирует запуск, тесты, ошибки и границы модулей.
- Мини-пример:

```python
metadata = {
    "commit": get_git_commit_hash(),
    "seed": 42,
    "params": model_params,
    "data_snapshot": data_snapshot_id,
}
```

## Хвост на конец итерации: SQL/runtime

Этот блок не является основной темой `iteration_06`. Его место - после
минимального закрытия темы детерминизма и возврата `unit_smoke` в зеленое
состояние.

Что нужно было проверить в конце итерации:

- состояние `move_txs_back`, если процесс еще актуален;
- фактическое состояние `TXS_MOVED`;
- наличие обязательных индексов `data_table`;
- отсутствие лишних `service_*` таблиц после maintenance;
- необходимость и результат `VACUUM` / `ANALYZE`;
- остаточный смысл legacy-сценария `moving_txs`.

Для любых действий с большими таблицами, `move_txs_back`, индексами, `VACUUM`,
`ANALYZE`, `wallet_stats`, `Btc_block_time_price` или массовыми переносами
действует правило:

- сначала design review альтернатив;
- затем выбор варианта пользователем;
- только потом реализация рискованной maintenance-операции.

Физический `moving_txs` остается legacy-путем. Новую модель low-tx фильтрации
нужно проектировать вокруг `data_table + wallet_stats`, без массового
физического переноса строк между рабочими таблицами.

### Фиксация состояния после `move_txs_back`

Дата промежуточной проверки: 2026-04-28.

Что подтверждено логом `logs/80.log`:

- run_id: `80`;
- сценарий: `service.move_txs_back`;
- перенесено из `few_tx_wallets` в `data_table`: `73_053_461` строк;
- progress: `100.00%`;
- финальный батч: `74/74`;
- `TXS_MOVED` обновлен на `False`;
- служебные таблицы move_txs удалены.

Что подтверждено прямой безопасной проверкой SQLite без полного `COUNT(*)`:

- БД: `C:/blocks_sql_data/blocks_sql_data_db.db`;
- размер основного файла БД: около `275_404_869_632` байт;
- `TXS_MOVED = False` в `settings/sql.py`;
- таблицы `data_table` и `few_tx_wallets` существуют;
- `data_table` содержит строки (`SELECT 1 ... LIMIT 1`);
- `few_tx_wallets` не содержит строк (`SELECT 1 ... LIMIT 1`);
- service-таблицы отсутствуют;
- WAL-файл существует, но размер `0`;
- SHM-файл существует, размер `32768`.

Финальная проверка после завершения maintenance: 2026-04-30.

Что подтверждено логом `logs/80.log`:

- `VACUUM` завершен: `2026-04-30 05:53:27`;
- `ANALYZE` завершен: `2026-04-30 05:56:46`;
- `move_txs_back` завершен успешно;
- stage `service.move_txs_back` закрыт со статусом `success`;
- run `80` закрыт со статусом `success`;
- длительность run: `33:35:30`.

Что подтверждено безопасной read-only проверкой SQLite без полного `COUNT(*)`:

- активный путь БД: `C:/blocks_sql_data/blocks_sql_data_db.db`;
- размер основного файла БД после `VACUUM`: `267_293_802_496` байт;
- `journal_mode = wal`;
- `page_count = 65_257_276`;
- `page_size = 4096`;
- `data_table` содержит строки (`SELECT 1 ... LIMIT 1`);
- `few_tx_wallets` существует, но не содержит строк (`SELECT 1 ... LIMIT 1`);
- service-таблицы отсутствуют;
- обязательные индексы `data_table` присутствуют:
  - `idx_wallet_id`;
  - `idx_block_height`;
  - `idx_txs_blocktime`;
  - `idx_block_height_wallet_id`;
- `missing_required_indexes = []`;
- `sqlite_stat1` существует;
- статистика `sqlite_stat1` для `data_table` есть:
  - `idx_block_height`;
  - `idx_block_height_wallet_id`;
  - `idx_txs_blocktime`;
  - `idx_wallet_id`;
- `TXS_MOVED = False` в `settings/sql.py`.

Полный `PRAGMA quick_check` не включен в финальный быстрый чеклист: на текущем
размере БД это дорогой полный scan, не smoke-проверка.

### Cleanup после завершения SQLite maintenance

После полного завершения процесса `move_txs_back` / `VACUUM` / `ANALYZE`
удалены старые пустые файлы БД от неактуального имени
`blocks_sql_data_db.sqlite3`:

- `C:/blocks_sql_data/blocks_sql_data_db.sqlite3`;
- `C:/blocks_sql_data/blocks_sql_data_db.sqlite3-shm`;
- `C:/blocks_sql_data/blocks_sql_data_db.sqlite3-wal`.

Перед удалением было проверено, что активный путь проекта указывает на
`C:/blocks_sql_data/blocks_sql_data_db.db`, а не на `.sqlite3`.

Не удалять активные файлы:

- `C:/blocks_sql_data/blocks_sql_data_db.db`;
- `C:/blocks_sql_data/blocks_sql_data_db.db-shm`;
- `C:/blocks_sql_data/blocks_sql_data_db.db-wal`.

Результат cleanup на 2026-04-30:

- старые `blocks_sql_data_db.sqlite3*` удалены;
- активная БД сохранена;
- активные файлы после cleanup:
  - `C:/blocks_sql_data/blocks_sql_data_db.db`;
  - `C:/blocks_sql_data/blocks_sql_data_db.db-shm`;
  - `C:/blocks_sql_data/blocks_sql_data_db.db-wal`;
- активный WAL после завершения процесса имеет размер `0`.

