# Iteration 04

## Тема

Errors and contracts of modules

## Цель итерации

Сделать поведение ошибок в проекте предсказуемым:
- явно разделить ожидаемые сбои инфраструктуры, ошибки валидации и внутренние ошибки выполнения;
- перестать "проглатывать" критичные сбои после одного `logger.error(...)`;
- сделать fail-fast на невалидных входах и плохих состояниях;
- закрепить, где модуль должен логировать, а где обязан пробрасывать исключение выше.

## Контекст старта

- `iteration_03` закрыта по основному результату.
- Хвосты по parser lifecycle и tracker-stage cleanup не являются блокером для старта `iteration_04`.
- Эти хвосты остаются в контексте как примеры модулей, где особенно важно уточнить контракты ошибок.

## Затронутые темы

- exception categories
- fail-fast
- module contracts
- logging vs raising
- runtime boundary handling

## Краткая теория

- Логгер и исключения решают разные задачи:
  - логгер фиксирует контекст;
  - исключение управляет потоком выполнения.
- Если модуль поймал исключение, залогировал его и не пробросил дальше, внешний orchestrator может ошибочно считать сценарий успешным.
- Fail-fast означает, что невалидный вход или сломанная инфраструктура должны ломать сценарий как можно ближе к месту обнаружения, а не превращаться в "тихий" fallback без явного договора.
- Граница ответственности обычно такая:
  - низкоуровневый модуль валидирует вход и поднимает осмысленное исключение;
  - orchestration-слой решает, что делать со сбоем целиком;
  - верхняя runtime-граница логирует финальный статус run.

## Предварительный диагноз

- В [main_functions.py](I:\projects\trade_app_project\main_functions.py) `run_parser_asyncio()` логирует ошибку парсера, но не пробрасывает ее выше, поэтому внешний lifecycle может потерять факт критичного сбоя.
- В [modules/blockchain_parser/main_parser.py](I:\projects\trade_app_project\modules\blockchain_parser\main_parser.py) парсер в `except` пишет ошибку в лог, но не завершает сценарий исключением, из-за чего контракт ошибки размыт.
- В [modules/blockchain_parser/async_parser_functions.py](I:\projects\trade_app_project\modules\blockchain_parser\async_parser_functions.py) много generic `Exception`, возвратов `None` после ошибок и смешения retry/logging/error-flow.
- В [modules/blocks_db_servises/db_servise_funcs.py](I:\projects\trade_app_project\modules\blocks_db_servises\db_servise_funcs.py) есть `raise Exception(...)`, `raise e` и несколько мест, где ошибка только логируется и теряется.

## Кандидаты на первый срез

- `main.py`
- `main_functions.py`
- `modules/blockchain_parser/main_parser.py`
- `modules/blockchain_parser/async_parser_functions.py`
- `modules/blocks_db_servises/db_servise_funcs.py`

## Вариант вмешательства на старте

- Начать с `Minimal patch`.
- Сначала договориться о 2-3 базовых категориях исключений и о том, где сценарий обязан падать, а где допустим retry.
- Первый практический срез логично сделать вокруг parser flow, потому что там одновременно видны и long-running lifecycle, и размытые границы ошибок.

## Черновой DoD

- Критичные ошибки parser flow не теряются после логирования.
- Generic `Exception` в ключевых runtime-гранях сокращены или заменены на более явные категории.
- Для 1-2 важных модулей зафиксирован понятный контракт:
  - что считается невалидным входом;
  - что считается инфраструктурным сбоем;
  - где ошибка логируется;
  - где ошибка пробрасывается выше.
- Итог итерации зафиксирован в `docs/iterations/iteration_04.md`.

## Что сделано на текущем этапе

- Для parser flow доведен базовый failure path:
  - низкоуровневая ошибка больше не должна оставаться только в `logger.error(...)`;
  - критичная ошибка доходит до orchestration-слоя parser run;
  - run получает честный `status=error`, а не "тихий" успех.
- В [main.py](I:\projects\trade_app_project\main.py), [main_functions.py](I:\projects\trade_app_project\main_functions.py) и [modules/blockchain_parser/main_parser.py](I:\projects\trade_app_project\modules\blockchain_parser\main_parser.py):
  - `right_now_test` переведен на контролируемый запуск parser thread с ожиданием завершения;
  - `parser()` больше не проглатывает критичную ошибку;
  - `run_parser_asyncio()` фиксирует `run_finished status=error` и отправляет `parser_status='completed with error'`.
- Путь к SQLite переведен в runtime/env-конфиг:
  - `BLOCKS_SQL_DATA` больше не зависит от старого project-local hardcode;
  - путь берется из `.env` через `settings/runtime.py`.
- Для сценария [modules/sql_funcs/moving_txs.py](I:\projects\trade_app_project\modules\sql_funcs\moving_txs.py):
  - критичные шаги переноса и перестройки данных больше не должны тихо продолжаться после ошибки;
  - диагностические и tuning-операции оставлены мягкими, если их сбой не ломает логическую корректность сценария.
- Для сценария `param_grid`:
  - запуск больше не начинается молча без входного grid-конфига;
  - ошибки подготовки данных и ошибки worker-пула не должны растворяться в частичном результате;
  - пустой итоговый набор результатов считается ошибкой сценария.
- Для сценария `converge_elasticnet`:
  - тест больше не считается корректным, если отсутствуют входные parquet-данные;
  - пустые итоговые dataframes считаются ошибкой сценария;
  - Dask client закрывается в `finally`, даже если подготовка данных упала.
- Для `main_pipeline`:
  - старт Flask уже проверяется как критичный шаг запуска;
  - updater не должен молча проходить при пустом обновлении цен;
  - пересчет `update_peaks()` больше не должен тихо пропускать устаревшие пики только потому, что parquet-файл уже существует;
  - запуск обучения больше не должен начинаться в неявном состоянии без новой модели.

## Текущий договор ошибок

### Parser flow

- Критичная ошибка в helper-слое:
  - логируется локально;
  - затем пробрасывается выше через `raise`.
- `parser()`:
  - завершает текущий tracker-stage как `error`;
  - пишет лог уровня parser;
  - снова пробрасывает ошибку выше.
- `run_parser_asyncio()`:
  - завершает весь run как `error`;
  - пишет `run_finished`;
  - отправляет `parser_status='completed with error'`.

### Helper-слой parser/db

- В [modules/blockchain_parser/async_parser_functions.py](I:\projects\trade_app_project\modules\blockchain_parser\async_parser_functions.py):
  - fail-fast оставлен для критичных операций:
    - `async_vacuum_analyze`
    - `async_set_foreign_keys`
    - `async_create_indexes`
    - `async_create_table`
    - `async_print_db_schema`
    - `async_get_existing_last_block`
    - финальное исчерпание retry в `sync_rpc_connection` / `async_rpc_connection`
    - `async_check_block_height_data`
    - `async_save_data_to_db`
  - soft-fail оставлен для допущенных настроечных операций:
    - `set_wal_mode`
    - `async_set_cache_size`
    - `async_set_synchronous_normal`
    - локальные retry-ветки до исчерпания попыток.
- В [modules/blocks_db_servises/db_servise_funcs.py](I:\projects\trade_app_project\modules\blocks_db_servises\db_servise_funcs.py):
  - soft-fail оставлен для:
    - `async_set_journal_mode_wal`
    - `async_vacuum_analyze`
    - `async_set_foreign_keys`
    - `async_set_cache_size`
    - `async_set_synchronous_normal`
    - `async_print_db_schema`
  - fail-fast оставлен для:
    - `async_create_indexes`
    - `async_create_table`
    - `async_alter_table_set_primary_key`
- В [modules/sql_funcs/moving_txs.py](I:\projects\trade_app_project\modules\sql_funcs\moving_txs.py):
  - fail-fast оставлен для:
    - `check_db`
    - `return_few_tx_wallets_to_data_table`
    - `create_indexes`
    - `create_target_table`
    - `create_temp_wallets_table`
    - `process_wallets`
    - `process_wallets_batch`
  - soft-fail оставлен для:
    - `get_count_in_table`
    - `optimize_db`
- В `param_grid`-цепочке:
  - fail-fast оставлен для:
    - отсутствующего или пустого param grid в `service_funcs.check_for_new_param_grid`
    - пустых временных интервалов в `orchestrator.teaching_with_param_grid_orchestrator`
    - ошибок worker-пула `ProcessPoolExecutor`
    - пустого финального результата `models_statistic_result_df`
    - отсутствующего или неподдержанного `correlation_type` в `data_operations.calculate_correlations_of_wallets`
  - soft-fail оставлен для:
    - загрузки уже существующих parquet-файлов корреляции, потому что там есть честный fallback на пересборку данных
- В `converge_elasticnet`:
  - fail-fast оставлен для:
    - отсутствующих parquet-директорий с тестовыми входными данными
    - пустых dataframes после подготовки teach/profit-test данных
  - soft-fail не добавлялся: сценарий тестовый и должен честно завершаться `error`, если тест не выполнен
- В `main_pipeline`:
  - fail-fast оставлен для:
    - неудачного старта Flask
    - пустого обновления BTC price data в `clean_raw_data`
    - пустого входного dataframe при пересчете peaks
    - отсутствующей директории или файла новой модели в `check_for_new_models`
    - неподдержанного `pkl`-пути обучения
  - soft-fail не добавлялся для этих шагов, потому что без них pipeline теряет смысл как целостный сценарий

## Что еще не закрыто

- Договор по критичности некоторых helper-функций в parser/db-слое пока локальный и минимальный; он еще не оформлен в единый набор exception-категорий.
- В проекте по-прежнему остаются generic `Exception` в других модулях вне текущего среза.
- Итерация пока не закрыта полностью:
  - нужно либо зафиксировать еще 1-2 модуля с явным контрактом ошибок;
  - либо обновить docs итоговым DoD и статусом после следующего подэтапа.

## Итог по факту

- В рамках `iteration_04` уже проведен не один локальный patch, а целая серия связанных срезов по ключевым сценариям проекта:
  - `parser flow`
  - `async_parser_functions.py`
  - `db_servise_funcs.py`
  - `moving_txs`
  - `param_grid`
  - `converge_elasticnet`
  - критичные хвосты `main_pipeline`
- Основной практический результат итерации достигнут:
  - критичные ошибки в ключевых сценариях заметно реже остаются только в `logger.error(...)`;
  - orchestration-слой чаще получает честный `error`, а не "тихий" успех;
  - несколько runtime-сценариев теперь имеют явный fail-fast contract.
- Побочный, но важный результат:
  - по ходу итерации отдельно прояснены Python-механики `raise`, propagation исключений и различие между logging и control flow.

## Оценка готовности к следующей итерации

- С инженерной точки зрения переход к `iteration_05` уже допустим.
- Причина:
  - цель четвертой итерации была не в полной глобальной error-taxonomy проекта, а в том, чтобы убрать самые опасные silent-failure паттерны и сделать обработку ошибок предсказуемее в ключевых сценариях;
  - этот результат уже получен.
- Что остается хвостом и не должно блокировать старт пятой итерации:
  - единые локальные exception-категории на весь проект;
  - остаточные `generic Exception` вне уже пройденных сценариев;
  - дальнейшая точечная шлифовка helper-функций.
- Практический вывод:
  - `iteration_04` можно считать **достаточно завершенной для перехода к iteration_05**;
  - оставшиеся хвосты разумно перевести в backlog/дошлифовку, а не держать ими открытой всю итерацию.

## Industry note (de-facto alternatives)

- Выбранный подход в итерации: локальные exception-категории и явный fail-fast на runtime-границах.
- Альтернатива (de-facto): единая иерархия `AppError`/`DomainError`/`InfrastructureError` на весь проект с централизованным mapping в CLI/API boundary.
- Почему не берем сейчас: для текущего проекта важнее сначала убрать тихое проглатывание ошибок в ключевых сценариях, чем сразу строить полную error taxonomy.
- Мини-пример:
  ```python
  class InfrastructureError(RuntimeError):
      pass

  if rpc_connection is None:
      raise InfrastructureError("RPC connection is not available")
  ```
