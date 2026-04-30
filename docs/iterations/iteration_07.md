# Iteration 07 - Module responsibility boundaries

## Тема

Границы ответственности модулей.

## Junior+ компетенция

Junior+ умеет отделять orchestration от бизнес-логики и I/O, удерживать
модули в понятных границах и объяснять, где должен находиться конкретный
тип поведения.

## Статус

Completed

## Контекст старта

- `iteration_06` закрыла детерминизм, experiment metadata, runtime bootstrap,
  CLI cleanup и быстрый `unit_smoke` сигнал.
- `iteration_06` слита в `main_branch` и запушена на origin.
- Рабочая ветка седьмой итерации:
  `feature/iteration-07-module-responsibility-boundaries`.
- На старте ветка создана от актуальной `main_branch`.
- В проекте уже видны кандидаты на разбор границ:
  - `main.py`;
  - `runtime_scenarios.py`;
  - `modules/teach_and_update_models/orchestrator.py`;
  - `modules/logger/runtime_bootstrap.py`;
  - CLI слой в `cli_args.py`;
  - runtime/logging/experiment metadata слой.

## Что уже частично выполнено в `iteration_06`

Часть работы, которая тематически относится к `iteration_07`, была сделана
раньше как практическая необходимость шестой итерации. Поэтому седьмая
итерация не должна повторно "облегчать `main.py`" с нуля.

Уже выполнено:

- `main.py` очищен от argparse-логики;
- CLI parsing и базовая CLI validation вынесены в `cli_args.py`;
- старт runtime logging и закрытие run вынесены в
  `modules/logger/runtime_bootstrap.py`;
- лишняя tracker-обвязка убрана из `main.py`;
- stage tracking для service-сценариев упрощен через `tracked_stage(...)`;
- legacy `return_few_tx_wallets` сценарий убран из CLI;
- `main-pipeline` оставлен обычной runtime-командой без искусственного
  `--seed`, потому что это не тестовый deterministic slice;
- `param-grid` получил явные `--seed` и `--test-fraction`;
- добавлены быстрые тесты на CLI contracts, runtime bootstrap, tracker
  metadata и experiment metadata.

Вывод для `iteration_07`:

- облегчение `main.py` уже частично выполнено;
- текущая задача - не повторять сделанное, а уточнить оставшуюся границу:
  где должен жить scenario dispatch и какие обязанности все еще лежат в
  `runtime_scenarios.py` / ML `orchestrator.py`;
- если `main.py` трогать дальше, то только маленьким срезом: например,
  вынести dispatch в тестируемую функцию без изменения runtime behavior.

## Цель итерации

Сделать границы между entrypoint, orchestration, бизнес-логикой и I/O
понятнее без большого rewrite.

Практический фокус:

- уточнить, что должно оставаться в `main.py`;
- отделить CLI parsing от runtime orchestration;
- отделить orchestration от вычислительных/pure-ish функций там, где это
  безопасно;
- уменьшить риск циклических импортов и скрытых side effects;
- улучшить тестируемость P0/P1-границ без Redis, Bitcoin Core и большой БД.

## Затронутые темы

- orchestration vs business logic;
- entrypoint boundaries;
- I/O boundaries;
- side effects;
- import boundaries;
- testable seams;
- agent workflow infrastructure as unexpected iteration support work.

## Непредусмотренный пункт на старте итерации

Перед практической работой по модульным границам была выполнена отдельная
инфраструктурная работа по правилам взаимодействия с Codex:

- создан корневой `AGENTS.md`;
- созданы repo-scoped skills в `.agents/skills/`;
- оформлены workflow:
  - `data-pipeline-safety-check`;
  - `discuss-plan-execute`;
  - `review-python-module`;
  - `iteration-workflow`;
  - `experiment-protocol`;
- русское пояснение вынесено в `docs/agents_skills_translate_ru.md`;
- decision records для экспериментов вынесены в `docs/experiments/`;
- старые черновики `docs/AGENTS_demo.md` и `docs/agents_skills_demo.md`
  удалены после переноса полезного содержания.

Этот пункт не был исходной темой `iteration_07`, но он влияет на то, как
дальше вести итерацию: теперь для risky DB задач, экспериментов, ревью и
закрытия итераций есть отдельные agent workflows.

## Короткая теория перед практикой

Граница ответственности модуля отвечает на вопрос: "какое решение этот слой
имеет право принимать?"

Рабочее разделение для проекта:

- entrypoint (`main.py`) принимает запуск процесса, вызывает CLI parsing,
  поднимает runtime logging и делегирует выбранный сценарий дальше;
- CLI слой (`cli_args.py`) знает только синтаксис команд, допустимые
  комбинации аргументов и базовую валидацию ввода пользователя;
- orchestration слой решает порядок шагов: например, сначала проверить
  индексы, потом запустить Flask, обновить цены, подготовить пики и запустить
  обучение;
- бизнес-логика считает результат по входным данным: например, выбирает
  параметры модели, готовит признаки, считает profit test, форматирует summary;
- I/O layer читает и пишет внешние системы: SQLite, parquet/json-файлы, Redis,
  Bitcoin Core, Flask, logs, model artifacts;
- side effect - любое действие, которое меняет внешний мир или зависит от него:
  старт потока, запись файла, SQL-запрос, логирование, Redis message, запуск
  Flask, чтение текущего run tracker;
- tests должны по возможности цепляться за стабильные границы, а не за
  случайные внутренние детали.

### Проектные примеры

- `main.py` как entrypoint: нормально, что он вызывает `parse_args()`,
  `start_runtime_logging(args)` и общий `try/except/finally`. Менее идеально,
  что он сам содержит dispatch деталей каждого сценария: `main-pipeline`,
  `param-grid`, `--start_parser`, `test ...`. Legacy `--service` был удален
  отдельным cleanup-срезом этой итерации.
- `cli_args.py` как CLI layer: сейчас граница хорошая - файл строит parser,
  проверяет несовместимые режимы и возвращает `argparse.Namespace`. Он не
  запускает Redis, БД, Flask или обучение.
- `runtime_bootstrap.py` как runtime/logging layer: файл отвечает за создание
  `RunTracker`, setup logging, metadata и закрытие run/stage. Это side-effect
  слой, но его side effects тематически собраны в одном месте.
- `runtime_scenarios.py` как legacy orchestration/infrastructure bucket: здесь
  одновременно есть запуск Redis, BTC monitor, parser threads, Flask,
  пере-сохранение JSON, запуск обучения, param-grid wrapper и integration-live
  stage tracking. Это главный кандидат на аккуратное разделение.
- `modules/teach_and_update_models/orchestrator.py` как ML orchestration:
  файл управляет порядком ML-шагов, но также читает/пишет parquet, меняет
  process cwd, проверяет SQL индексы, обновляет runtime metadata и запускает
  `ProcessPoolExecutor`. Это не ошибка само по себе, но границы внутри файла
  плотные и требуют осторожного среза.

## Предварительный диагноз

- P0/P1: после `iteration_06` `main.py` стал тоньше, но нужно проверить, не
  остались ли orchestration обязанности в неподходящих слоях.
- P1: `runtime_scenarios.py` исторически смешивал orchestration, infrastructure
  calls и side effects; это главный кандидат на разбор.
- P1: ML orchestration и data operations требуют аккуратного разделения:
  нельзя одновременно менять поведение pipeline и переносить код ради красоты.
- P1: новые agent workflows помогают процессу, но их нужно считать
  инфраструктурным контекстом, а не заменой инженерного анализа кода.

## Карта текущих границ

### `main.py`

Текущая роль:

- entrypoint процесса;
- вызывает `parse_args()`;
- стартует runtime logging через `start_runtime_logging(args)`;
- держит общий `try/except/finally`;
- закрывает run через `finish_runtime_success`, `finish_runtime_error`,
  `finish_runtime_interrupted`;
- вызывает `stop_logging()` в `finally`;
- выбирает сценарий запуска по `args.command` и `args.start_parser`;
- для `main-pipeline` делегирует порядок шагов в
  `runtime_scenarios.prepare_training_data_and_train_new_model()`.

Что смешано:

- entrypoint и command dispatch находятся в одном файле;
- детали порядка шагов `main-pipeline` уже вынесены из `main.py` в
  `runtime_scenarios.py`;
- `main.py` напрямую импортирует сценарные зависимости внутри веток запуска;
- legacy service-команды `move_txs` / `move_txs_back` больше не находятся в
  `main.py`: пользовательский entrypoint удален.

Оценка:

- после `iteration_06` файл уже достаточно тонкий для старта;
- первый срез `iteration_07` убрал из `main.py` знание порядка шагов
  `main-pipeline`;
- оставшийся вопрос - выносить ли весь scenario dispatch в отдельную
  тестируемую функцию/модуль.

### `cli_args.py`

Текущая роль:

- строит `argparse.ArgumentParser`;
- описывает top-level сценарии;
- валидирует, что выбран ровно один режим запуска;
- валидирует `downloaded-from-btc-data blocks_count`;
- возвращает `argparse.Namespace`.

Что смешано:

- существенного смешения с runtime сейчас нет;
- CLI help содержит русско-английские описания, но это не архитектурный риск;
- `test_downloaded_from_btc_data` остался в `EPILOG` как старое имя, тогда как
  фактическая команда сейчас `test downloaded-from-btc-data`.

Оценка:

- граница хорошая: файл не запускает side effects;
- возможный маленький срез - уточнить help/epilog или добавить тест на
  конфликт top-level режимов, если решим улучшать CLI-контракт.

### `runtime_scenarios.py`

Примечание: файл переименован из `main_functions.py` в `runtime_scenarios.py`,
чтобы зафиксировать целевую роль - сценарии запуска, вызываемые из `main.py`.

Текущая роль:

- scenario слой для `main.py`;
- держит порядок шагов runtime-сценариев;
- вызывает доменные runtime entrypoints:
  - parser lifecycle из `modules/blockchain_parser/parser_runtime.py`;
  - Flask startup из `modules/flask_module/flask_runtime.py`;
  - BTC price update wrapper из `modules/bts_price_updater/runtime.py`;
  - training entrypoints из
    `modules/teach_and_update_models/training_entrypoints.py`;
- лениво подключает integration-live scenario helper только при запуске
  `test downloaded-from-btc-data`.

Что смешано:

- orchestration и runtime side effects все еще связаны через прямые вызовы
  entrypoint-функций;
- `runtime_scenarios.py` знает, какие доменные entrypoints нужны каждому
  top-level сценарию;
- для parser-сценария держит keep-alive loop, потому что это часть
  пользовательского runtime-сценария, а не ответственность `main.py`.

Оценка:

- после дополнительного среза файл стал ближе к целевой роли:
  "сценарии запуска, вызываемые из `main.py`";
- тяжелые side effects теперь лежат в доменных runtime/helper модулях;
- любые дальнейшие изменения вокруг parser, Redis и BTC Core все еще считать
  runtime-sensitive.

### `modules/logger/runtime_bootstrap.py`

Текущая роль:

- стартует logging и `RunTracker`;
- собирает initial experiment metadata;
- логирует `run_started`;
- обновляет runtime metadata;
- предоставляет `tracked_stage(...)`;
- закрывает success/error/interrupted runs;
- закрывает активный stage при error/interrupted.

Что смешано:

- runtime lifecycle и logging side effects намеренно находятся вместе;
- модуль знает про `RunTracker`, logger module и experiment metadata;
- бизнес-логики pipeline здесь нет.

Оценка:

- граница в целом удачная: side effects собраны по теме runtime/logging;
- ближайший риск не в этом файле, а в том, что другие модули напрямую
  используют tracker/logger и повторяют stage lifecycle вручную.

### `modules/teach_and_update_models/orchestrator.py`

Текущая роль:

- orchestrator обучения модели;
- orchestrator param-grid;
- выбирает model class;
- вызывает data operations;
- запускает train/evaluate/save steps;
- управляет tracker stages внутри ML pipeline;
- читает/пишет parquet cache/results;
- обновляет runtime metadata по grid params;
- запускает `ProcessPoolExecutor` для param-grid workers.

Что смешано:

- orchestration и I/O: parquet cache, result artifacts, `os.makedirs`,
  `pd.read_parquet`, `to_parquet`;
- orchestration и runtime: tracker stage start/finish, metadata updates;
- orchestration и business rules: группировка grid по `correlation_type`,
  выбор `ElasticNet`, проверка пустых данных;
- module import side effect: `os.chdir(script_dir)` выполняется на import;
- SQL/data safety context: проверка индексов `data_table` вызывается прямо из
  ML orchestration.

Оценка:

- файл важный, но рискованный для первого среза;
- безопасная работа здесь - сначала документировать внутренние подграницы и
  тестировать pure/helper функции;
- перенос parquet/cache или multiprocessing логики лучше делать отдельным
  маленьким шагом после выбора практического среза.

## Где границы смешаны сильнее всего

- `main.py`: entrypoint + scenario dispatch.
- `runtime_scenarios.py`: orchestration + infrastructure I/O + runtime tracking +
  global/thread state.
- `orchestrator.py`: ML orchestration + artifact I/O + tracker stage lifecycle +
  param-grid business rules.

Менее проблемные границы:

- `cli_args.py`: почти чистый CLI parsing/validation слой.
- `runtime_bootstrap.py`: side effects есть, но они собраны вокруг одной темы -
  runtime/logging lifecycle.

## Рекомендованный первый практический срез после карты

Вариант A, самый безопасный:

- оставить runtime-код без изменений;
- обновить `cli_args.py` help/epilog и добавить 1 тест на конфликт top-level
  режимов;
- зафиксировать, что CLI layer остается без side effects.

Вариант B, более полезный для темы итерации:

- вынести scenario dispatch из `main.py` в маленькую функцию, например
  `run_selected_scenario(args, tracker)`;
- покрыть dispatch monkeypatch-тестами без Redis/BTC/Flask/SQL;
- оставить сами scenario implementations на месте.

Вариант C, осторожный срез по `runtime_scenarios.py`:

- вынести `format_downloaded_from_btc_stage_details` и/или stage tracking
  integration-live сценария в отдельную helper-границу;
- добавить pure test на формат details;
- не трогать parser/Redis/BTC/Flask lifecycle.

Рекомендация: начать с варианта B или C, учитывая уже выполненный в
`iteration_06` cleanup. Вариант B не должен снова "чистить `main.py`", а только
вынести оставшийся scenario dispatch в тестируемую границу, если это окупается.
Вариант C безопаснее показывает разницу business/helper logic и I/O внутри
самого смешанного файла.

## Выбранный первый практический срез

Выбран маленький срез из варианта B:

- не переносить весь dispatch сразу;
- вынести только порядок шагов `main-pipeline` из `main.py`;
- добавить `runtime_scenarios.prepare_training_data_and_train_new_model()`;
- оставить локальные импорты сценарных зависимостей внутри `runtime_scenarios.py`;
- покрыть порядок шагов быстрым тестом без Flask, BTC Core, Redis и SQLite.

Почему так:

- `main.py` перестает знать, из каких внутренних шагов состоит основной
  pipeline;
- проблема локальных импортов не исчезает, а переезжает в `runtime_scenarios.py`;
- это приемлемо как промежуточный шаг, потому что следующий разбор как раз
  будет посвящен `runtime_scenarios.py`;
- `start_btc_price_updater()` оставлен в этом сценарии: перед подготовкой peaks
  сценарий должен обновить/очистить price data, потому что обучение новой
  модели зависит от актуальных price/peaks artifacts;
- имя функции изменено на `prepare_training_data_and_train_new_model()`, чтобы
  не маскировать исследовательский/обучающий сценарий под общий main pipeline;
- файл `main_functions.py` переименован в `runtime_scenarios.py`;
- открытый вопрос: считать ли этот сценарий постоянным production process или
  исследовательской заготовкой. Временные окна обучения задаются не здесь, а в
  JSON модели через `time_params` и рассчитываются относительно последнего
  блока в `data_table`;
- пользовательский entrypoint `--service move_txs` / `--service move_txs_back`
  удален отдельным маленьким cleanup-срезом после явного решения пользователя;
- исторический контекст по физическому переносу txs зафиксирован в
  `docs/experiments/moving_txs_physical_split/`;
- legacy-модуль `modules/sql_funcs/moving_txs.py` и его старые unit-smoke
  helper tests перенесены в experiment folder как audit/recovery context;
- рабочие index-check функции сохранены в
  `modules/sql_funcs/data_table_indexes.py`, потому что они переиспользуются
  runtime-сценариями и smoke-тестами.

Промежуточная проверка после среза:

```powershell
python -m pytest tests\unit_smoke\test_runtime_scenarios.py tests\unit_smoke\test_main.py -q
python -m pytest tests\unit_smoke -q
```

Результат: `9 passed` для точечных тестов, `42 passed, 1 warning` для всего
`unit_smoke`. Предупреждение осталось прежним: pandas `DataFrameGroupBy.apply`
в `modules/teach_and_update_models/data_operations.py`.

### Cleanup maintenance entrypoint

После обсуждения принято решение удалить пользовательский CLI entrypoint для
legacy physical split:

- из `cli_args.py` удален `--service`;
- из `main.py` удалены ветки `args.service == "move_txs"` и
  `args.service == "move_txs_back"`;
- `tests/unit_smoke/test_main.py` обновлен: legacy `--service move_txs` теперь
  должен отклоняться CLI parser-ом;
- `docs/maintenance_guidelines.md` обновлен: физический перенос txs признан
  слабо жизнеспособным operational pattern;
- добавлен experiment/decision record
  `docs/experiments/moving_txs_physical_split/README.md`.

Важно: это не выполняло SQL, не запускало maintenance и не мутировало БД.

Дополнительный cleanup рабочего кода:

- `modules/sql_funcs/moving_txs.py` перенесен в
  `docs/experiments/moving_txs_physical_split/legacy_moving_txs.py`;
- `tests/unit_smoke/test_moving_txs.py` перенесен в
  `docs/experiments/moving_txs_physical_split/legacy_test_moving_txs.py`;
- из рабочего кода удалены импорты `modules.sql_funcs.moving_txs`;
- переиспользуемые проверки индексов `data_table` вынесены в
  `modules/sql_funcs/data_table_indexes.py`;
- из `settings/sql.py` удалены batch-константы, которые использовались только
  архивированным physical split maintenance.

Проверка после переноса legacy-кода в experiment folder:

```powershell
python -m pytest tests\unit_smoke\test_sql_indexes_smoke.py tests\unit_smoke\test_live_db_indexes_warning.py tests\unit_smoke\test_main.py tests\unit_smoke\test_runtime_scenarios.py -q
python -c "import runtime_scenarios; import modules.teach_and_update_models.orchestrator as o; import modules.sql_funcs.data_table_indexes as d; print('imports ok')"
python -m pytest tests\unit_smoke -q
```

Результат: `11 passed` для затронутых smoke-тестов, `imports ok`,
`40 passed, 1 warning` для всего `unit_smoke`. Количество тестов уменьшилось с
`42` до `40`, потому что два legacy-теста physical split перенесены из рабочего
`tests/unit_smoke` в `docs/experiments/moving_txs_physical_split/` вместе с
архивированным кодом. Предупреждение осталось прежним: pandas
`DataFrameGroupBy.apply` в `modules/teach_and_update_models/data_operations.py`.

Проверка после cleanup:

```powershell
python -m pytest tests\unit_smoke\test_main.py tests\unit_smoke\test_runtime_scenarios.py -q
python -m pytest tests\unit_smoke -q
```

Результат: `9 passed` для точечных тестов, `42 passed, 1 warning` для всего
`unit_smoke`. Предупреждение то же: pandas `DataFrameGroupBy.apply` в
`modules/teach_and_update_models/data_operations.py`.

Проверка после переименования `main_functions.py` -> `runtime_scenarios.py`:

```powershell
python -m pytest tests\unit_smoke\test_main.py tests\unit_smoke\test_runtime_scenarios.py -q
python -c "import runtime_scenarios; print('runtime_scenarios import ok')"
python -m pytest tests\unit_smoke -q
```

Результат: `9 passed`, `runtime_scenarios import ok`, `40 passed, 1 warning`.
Предупреждение прежнее: pandas `DataFrameGroupBy.apply` в
`modules/teach_and_update_models/data_operations.py`.

### Дополнительный срез по комментариям в `runtime_scenarios.py`

После разбора пользовательских комментариев к функциям принято решение
оставить в `runtime_scenarios.py` только top-level сценарии, а support-код
разнести по доменным границам:

- parser/Redis/BTC lifecycle перенесен в
  `modules/blockchain_parser/parser_runtime.py`;
- Flask startup перенесен в `modules/flask_module/flask_runtime.py`;
- BTC price updater wrapper перенесен в `modules/bts_price_updater/runtime.py`;
- training wrappers и JSON normalize вынесены в
  `modules/teach_and_update_models/training_entrypoints.py`;
- integration-live formatting и stage tracking вынесены в
  `tests/integration_live/downloaded_from_btc_scenario.py`;
- `main.py` больше не держит keep-alive loop parser-сценария: это часть
  `runtime_scenarios.run_parser_monitor_scenario()`;
- integration-live helper импортируется лениво внутри соответствующего
  сценария, чтобы обычный import `runtime_scenarios` не подтягивал test-layer.
- ML training entrypoints тоже импортируются лениво внутри training-сценариев:
  это изолирует известный import side effect `orchestrator.py` с `os.chdir(...)`
  от parser и integration-live сценариев.

Смысл решения:

- `main.py` остается entrypoint + runtime bootstrap + выбор сценария;
- `runtime_scenarios.py` остается orchestration-слоем top-level сценариев;
- инфраструктурные side effects живут ближе к своим доменам;
- спорные technical debt notes не потеряны: они зафиксированы в
  `docs/iterations/iteration_13.md` с ссылками на текущие места поведения.

Проверка после разнесения support-кода:

```powershell
python -m pytest tests\unit_smoke\test_runtime_scenarios.py tests\unit_smoke\test_main.py -q
python -c "import os, importlib.util; import runtime_scenarios; import modules.blockchain_parser.parser_runtime as pr; import modules.flask_module.flask_runtime as fr; import modules.bts_price_updater.runtime as br; import tests.integration_live.downloaded_from_btc_scenario as ds; print('imports ok'); print(os.getcwd()); print(importlib.util.find_spec('tests.integration_live'))"
python -m pytest tests\unit_smoke -q
```

Результат: `12 passed`, `imports ok`, `43 passed, 1 warning`.
Предупреждение прежнее: pandas `DataFrameGroupBy.apply` в
`modules/teach_and_update_models/data_operations.py`.

Финальная smoke-защита границы import:

- добавлен тест
  `test_import_runtime_scenarios_does_not_change_cwd_or_load_lazy_scenario_modules`;
- тест запускает чистый Python subprocess и проверяет, что
  `import runtime_scenarios`:
  - не меняет current working directory;
  - не подтягивает `modules.teach_and_update_models.training_entrypoints`;
  - не подтягивает `modules.teach_and_update_models.orchestrator`;
  - не подтягивает `tests.integration_live.downloaded_from_btc_scenario`.

Финальный обзор `runtime_scenarios.py`:

- остались только:
  - `warn_data_table_indexes_for_scenario`;
  - `prepare_training_data_and_train_new_model`;
  - `run_param_grid_scenario`;
  - `run_parser_monitor_scenario`;
  - `run_downloaded_from_btc_data_scenario`;
- support/runtime/helper код вынесен из файла;
- оставшаяся `warn_data_table_indexes_for_scenario` считается допустимой
  маленькой общей preflight-оберткой scenario-слоя.

Финальная точечная проверка:

```powershell
python -m pytest tests\unit_smoke\test_runtime_scenarios.py tests\unit_smoke\test_main.py -q
python -m pytest tests\unit_smoke -q
```

Результат: `13 passed` для точечных тестов, `44 passed, 1 warning` для всего
`unit_smoke`. Предупреждение прежнее: pandas `DataFrameGroupBy.apply` в
`modules/teach_and_update_models/data_operations.py`.

## Итог итерации

Iteration 07 выполнила главный практический фокус:

- `main.py` стал тонким entrypoint/runtime wrapper и больше не знает порядок
  внутренних шагов сценариев;
- `main_functions.py` переименован в `runtime_scenarios.py` и приведен к роли
  top-level scenario orchestration;
- service/maintenance entrypoint physical split удален из рабочего CLI;
- legacy physical split код перенесен в experiment/audit context;
- support-код из бывшего `main_functions.py` разнесен по доменным runtime
  модулям;
- smoke-тесты фиксируют порядок сценариев и отсутствие import side effects.

Сознательно отложено:

- глубокий разбор `modules/teach_and_update_models/orchestrator.py`;
- policy parser restart / daemon thread lifecycle;
- модельный класс и контракт загрузки модели из grid/json;
- решение по старым/удаленным сценариям запуска, зафиксированное в
  `docs/iterations/iteration_13.md`.

## Кандидаты на первый срез

- `main.py` - проверить, что entrypoint остается тонким.
- `cli_args.py` - проверить, где заканчивается parsing и начинается runtime.
- `runtime_scenarios.py` - найти смешанные обязанности и side effects.
- `modules/teach_and_update_models/orchestrator.py` - оценить, где
  orchestration смешивается с model/data details.
- `modules/logger/runtime_bootstrap.py` - проверить границу runtime startup /
  shutdown.

## Варианты вмешательства

### Minimal patch

- Сделать обзор текущих границ.
- Выбрать 1-2 самые безопасные точки для локального улучшения.
- Добавить или уточнить smoke/unit тесты только для стабильных контрактов.

Плюсы: низкий риск, хорошо подходит после большого среза `iteration_06`.

Минусы: не решит всю архитектуру сразу.

### Medium refactor

- Выделить несколько helper/orchestration функций из `runtime_scenarios.py`.
- Уточнить слой CLI/runtime/orchestration.
- Добавить тесты на новые границы.

Плюсы: заметнее улучшит структуру.

Минусы: выше риск случайно поменять runtime behavior.

### Rewrite slice

- Пересобрать один крупный pipeline вокруг явных объектов/контрактов.

Плюсы: потенциально чище долгосрочно.

Минусы: слишком рискованно для старта итерации; сначала нужен обзор и
минимальный срез.

## Рекомендация на старт

Начать с `Minimal patch`.

Причина: тема итерации про границы ответственности, но после `iteration_06`
уже было много изменений в entrypoint/runtime/metadata. Сначала нужно
зафиксировать текущую карту границ, явно отметить уже выполненную часть и
выбрать маленький безопасный срез.

## Definition of Done

- [x] Текущие границы `main.py` / `cli_args.py` / `runtime_scenarios.py` /
  runtime/logging/orchestration описаны в документе итерации.
- [x] Зафиксировано, какая часть облегчения `main.py`, CLI cleanup и runtime
  bootstrap уже выполнена в `iteration_06`.
- [x] Выбран минимальный практический срез без крупного rewrite.
- [x] Внесены только scoped изменения, если они действительно нужны после
  обзора.
- [x] Для измененного поведения есть быстрый тест или явно зафиксировано,
  почему тест не нужен.
- [x] `python -m pytest tests\unit_smoke -q` проходит перед закрытием
  итерации, если были изменения в коде.
- [x] Итог, ограничения и хвосты зафиксированы в этом документе.

## Командная памятка

Быстрые smoke/regression тесты:

```powershell
python -m pytest tests\unit_smoke -q
```

Проверка текущей ветки:

```powershell
git branch --show-current
git status -sb
```
