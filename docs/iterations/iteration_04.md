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
