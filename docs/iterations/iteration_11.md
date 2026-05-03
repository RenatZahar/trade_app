# Iteration 11 - Notes and docs hygiene

## Тема

Ревизия и гигиена документации заметок в `docs/`.

## Junior+ компетенция

Junior+ умеет поддерживать рабочие заметки в актуальном и пригодном для ревью
состоянии: отделять актуальные решения от исторического контекста, фиксировать
статус задач, связывать заметки с кодом и не превращать `docs/` в свалку
непроверяемых наблюдений.

## Статус

Done

## Контекст старта

- `iteration_10` закрыта, запушена и слита в `main_branch`.
- Рабочая ветка одиннадцатой итерации:
  `feature/iteration-11-notes-docs-hygiene`.
- `main_branch` и `origin/main_branch` на старте указывают на один commit:
  `ef52d0c` (`Merge iteration 10 portfolio packaging`).
- В `docs/` уже есть:
  - `junior_plus_program.md` как процессный контракт программы;
  - `maintenance_guidelines.md` как source of truth для SQLite/data work;
  - `main_notes.md` как рабочие заметки на старте итерации; файл удален после
    переноса содержания в этот iteration artifact;
  - `agents_skills_translate_ru.md` как пользовательское объяснение правил;
  - `iterations/` с историей итераций;
  - `experiments/` для experiment records.
- Файлы `docs/*_translate_ru.md` являются user-facing объяснениями и не должны
  иметь больший приоритет, чем `AGENTS.md` или активные skills.
- Для больших данных, SQLite, bulk operations, индексов и maintenance задач
  продолжает действовать hard stop: сначала design review альтернатив, затем
  только выбранная реализация.

## Цель итерации

Привести рабочие заметки и внутреннюю документацию к состоянию, в котором их
можно быстро читать, ревьюить и использовать как навигацию по проекту:

- зафиксировать единый формат заметок в `docs/`:
  цель, контекст, решения, next steps;
- отделить актуальные решения от устаревших или исторических наблюдений;
- пометить статус задач и хвостов;
- связать заметки с кодом, сценариями запуска и уже существующими docs;
- не менять runtime behavior проекта в рамках этой итерации без отдельного
  выбора.

## Границы

В scope:

- содержимое бывшего `docs/main_notes.md`;
- при необходимости docs-only уточнения в `docs/iterations/*.md`;
- при необходимости docs-only уточнения в `docs/junior_plus_program.md`;
- ссылки из заметок на реальные модули, runtime scenarios, README и проверки;
- фиксация follow-up задач без реализации этих задач.

Не в scope:

- runtime refactor;
- изменение CLI, логирования, тестов или GitHub Actions;
- SQLite/data maintenance, migrations, индексы, `VACUUM`, `ANALYZE`;
- перенос private strategy logic в публичные документы;
- переписывание всех документов ради единого стиля;
- закрытие technical debt из итерации 13.

## Риски

- Можно случайно удалить исторический контекст, который еще нужен для roadmap.
- Docs cleanup легко расползается в архитектурный рефакторинг или technical debt
  work.
- Нельзя делать заметки красивее ценой потери проверяемости: каждая важная
  запись должна иметь статус, ссылку или понятный next step.
- Нужно не смешать agent instructions, user-facing explanations и roadmap notes.
- README после итерации 10 стал публичной витриной, поэтому внутренние заметки
  не должны дублировать его полностью.

## Варианты

### Minimal patch

- Перенести содержимое бывшего `docs/main_notes.md` в единый формат.
- Добавить статусы и короткие next steps.
- Не трогать остальные документы, кроме статуса текущей итерации.

Плюсы: низкий риск, быстро улучшает главную рабочую заметку.

Минусы: часть расхождений между документами может остаться.

### Medium docs pass

- Сделать `Minimal patch`.
- Добавить перекрестные ссылки между README, будущим backlog в iteration docs
  и релевантными process/safety docs.
- Пометить устаревшие или перенесенные заметки без удаления спорного контекста.

Плюсы: лучше навигация по проекту, меньше дублирования.

Минусы: выше риск scope creep и случайного переписывания лишнего.

### Rewrite slice

- Переписать структуру заметок в `docs/` как мини-документацию проекта:
  overview, decisions, backlog, operations, learning notes.

Плюсы: самый чистый долгосрочный результат.

Минусы: слишком широкий шаг для одной учебной итерации; высокий риск потерять
важные нюансы и смешать документацию с roadmap.

## Выбранный стартовый план

Начать с diagnosis-first подхода и выбрать масштаб после ревизии:

1. Просмотреть бывший `docs/main_notes.md`, README, русскую README, roadmap и
   релевантные iteration docs.
2. Составить диагноз по заметкам:
   - что актуально;
   - что устарело;
   - что дублирует другие документы;
   - какие записи требуют ссылки на код или сценарий запуска.
3. Предложить точечный `Minimal patch` как базовый вариант.
4. Если после диагноза видно, что навигация страдает сильнее, перейти к
   `Medium docs pass`.
5. Зафиксировать результат, README impact и remaining follow-up в этом файле.

## Детальный рабочий план

### Phase 1 - Inventory and diagnosis

Цель: понять фактическое состояние `docs/`, не переписывая документы наугад.

Действия:

1. Проверить рабочую ветку и чистоту worktree.
2. Составить inventory `docs/`:
   - process docs: `docs/junior_plus_program.md`, `docs/iterations/*.md`;
   - operational docs: `docs/maintenance_guidelines.md`;
   - working notes: бывший `docs/main_notes.md`;
   - user-facing explanations: `docs/*_translate_ru.md`;
   - experiment records: `docs/experiments/`.
3. Прочитать документы, которые задают контекст именно для iteration 11:
   - `README.md`;
   - `README.ru.md`;
   - бывший `docs/main_notes.md`;
   - `docs/junior_plus_program.md`;
   - `docs/iterations/iteration_10.md`;
   - `docs/iterations/iteration_11.md`;
   - `docs/iterations/iteration_12.md`;
   - `docs/iterations/iteration_13.md`.
4. Проверить, что ключевые ссылки из заметок соответствуют реальным зонам кода:
   - `main.py`;
   - `cli_args.py`;
   - `runtime_scenarios.py`;
   - `settings/runtime_contracts.py`;
   - `tests/unit_smoke`;
   - `modules/logger`.
5. Составить диагноз:
   - какие записи актуальны;
   - какие уже закрыты прошлыми итерациями;
   - какие перенесены в iteration 13;
   - какие требуют safety review перед реализацией;
   - какие стоит оставить только как historical context.

Ожидаемый артефакт: diagnosis summary в этом файле.

### Phase 2 - Choose intervention size

Цель: выбрать объем правок до переноса бывшего `docs/main_notes.md`.

Критерии выбора:

- `Minimal patch`, если проблема только в структуре бывшего `docs/main_notes.md`.
- `Medium docs pass`, если заметки нужно связать с README, roadmap,
  iteration 13 и safety rules.
- `Rewrite slice`, только если текущая структура мешает использовать `docs/`
  как рабочую навигацию. На старте считается нежелательным вариантом.

Текущая предварительная рекомендация после Phase 1: `Medium docs pass`.

### Phase 3 - Fold former `docs/main_notes.md` into iteration docs

Цель: сделать рабочую заметку пригодной для ревью и следующего действия.

Планируемая структура:

1. Назначение файла.
2. Правило приоритетов:
   - `AGENTS.md` и active skills выше;
   - README - публичная витрина;
   - iteration docs - история решений;
   - бывший `main_notes.md` - источник triage/backlog, но не постоянный файл.
3. Active notes:
   - каждая запись имеет статус, owner/context и next step.
4. Deferred to iteration 13:
   - old runtime scenarios;
   - data model / SQL performance;
   - public/private boundary;
   - repo tooling;
   - lint adoption.
5. Historical notes:
   - уже выполненные или устаревшие пункты, сохраненные только для контекста.
6. Related files and checks.

### Phase 4 - Cross-link only where useful

Цель: улучшить навигацию без переписывания всего `docs/`.

Возможные точечные правки:

- добавить перенесенным заметкам ссылки на README, iteration 13 и maintenance
  guidelines;
- при необходимости добавить в `iteration_11.md` результат diagnosis;
- не менять roadmap, если публичный статус и порядок итераций не изменились.

### Phase 5 - Closeout

Цель: зафиксировать результат итерации как инженерный артефакт.

Действия:

1. Обновить `iteration_11.md`:
   - chosen plan;
   - completed changes;
   - README impact;
   - checks;
   - Industry note;
   - DoD.
2. Проверить diff:
   - `git diff --check`;
   - review staged scope перед commit.
3. Запустить релевантную проверку:
   - для docs-only правки достаточно `git diff --check`;
   - `python -m pytest tests\unit_smoke -q` запускать только если правка
     меняет публичные команды, runtime docs или project facts, влияющие на
     README/CI expectations.
4. Commit и push текущей ветки.

## Phase 1 diagnosis summary

Статус: completed.

Наблюдения:

- бывший `docs/main_notes.md` смешивал:
  - старый backlog до работы с агентом;
  - фрагмент старого flag-based кода из `main.py`;
  - выполненные исторические пункты;
  - SQLite/data safety notes;
  - будущие идеи без статуса и next step.
- README после iteration 10 уже закрывает публичный overview, architecture,
  quickstart, runtime scenarios, logs/artifacts, tests/CI, known limits и
  roadmap. Поэтому перенесенные заметки не должны дублировать README целиком.
- Большая часть тяжелых технических идей уже лучше описана в
  `docs/iterations/iteration_13.md`, особенно:
  - legacy notebook/current pipeline comparison;
  - SQL performance review;
  - `data_table` / `few_tx_wallets` / `wallet_stats`;
  - old runtime scenarios from `main.py`;
  - public/private boundary;
  - repo tooling and lint adoption.
- Data/SQLite пункты из бывшего `docs/main_notes.md` должны остаться только как
  backlog references. Реализация таких задач требует отдельного
  `$data-pipeline-safety-check` и design review.
- Текущий supported CLI по коду:
  - `main-pipeline`;
  - `param-grid`;
  - `--start_parser`;
  - `test downloaded-from-btc-data`.
  Старый flag-block из бывшего `docs/main_notes.md` исторический и не должен
  выглядеть как актуальная инструкция запуска.
- `rg --files` в текущей среде вернул `Access is denied`; inventory выполнен
  через PowerShell `Get-ChildItem`.

Решение: использовать `Medium docs pass`, но держать фактические изменения
узкими: перенести содержимое `docs/main_notes.md` в этот iteration artifact,
дополнить недостающие future topics в `docs/iterations/iteration_13.md`, затем
удалить `docs/main_notes.md`, без runtime-кода и без data/database операций.

## Phase 2 decision and former `main_notes.md` triage

Статус: completed.

Оценка пользовательских предположений:

- `Backlog до работы с агентом`: предположение верное частично. Часть пунктов
  закрыта итерациями 1-10, часть остается актуальной только как future research
  или technical debt. Старые model/feature вопросы нельзя просто удалить:
  они связаны с будущим artifact-based сравнением pipeline.
- Пункты про `threshold = 0.3`, `Normalized_sell_amount` и
  `Normalized_buy_amount`: предположение верное. Они не должны оставаться
  бесконтекстными заметками; их нужно держать как future
  model/feature research в `iteration_13`. По коду видно, что
  `correlation_threshold` уже приходит через `filter_params`, а grid строится
  из model config, но семантику `correlation_threshold` / `threshold` /
  `decision_threshold` еще стоит проверить отдельно.
- `Доступ к аналитике по ссылке/доступу к проекту`: предположение верное. Это
  future product/deployment/security вопрос, завязанный на public/private
  boundary, а не задача текущей docs hygiene итерации.
- `Изучить корреляцию типов кошельков и импакта в пики`: предположение верное.
  Это research item для будущей model/data итерации рядом с actor/wallet-level
  aggregation.
- `Backlog после старта работы с агентом`: предположение верное. Старый
  flag-based запуск больше не актуален: поддерживаемые сценарии сейчас
  `main-pipeline`, `param-grid`, `--start_parser`,
  `test downloaded-from-btc-data`.
- `Выполнено (исторические заметки)`: удалять без следа не стоит. Эти пункты
  больше не должны выглядеть как backlog, но полезны как компактный список
  уже реализованных возможностей проекта.
- `Технические заметки`: предположение верное. Safety rule остается ссылкой на
  `docs/maintenance_guidelines.md`, а идеи по SQL/data/parser/runtime
  перенесены или связаны с `iteration_13`.

Что изменено:

- содержимое `docs/main_notes.md` перенесено в этот iteration artifact как
  triage/disposition record:
  - назначение файла;
  - итог ревизии;
  - таблица статусов старых заметок;
  - active deferred backlog;
  - historical implemented capabilities;
  - related files.
- `docs/main_notes.md` удаляется после переноса, чтобы не держать отдельный
  дублирующий документ.
- В `docs/iterations/iteration_13.md` добавлен блок backlog, перенесенный из
  бывшего `docs/main_notes.md`:
  - model and feature research;
  - analytics and access;
  - data retention and DB tooling;
  - parser/ZMQ notes.

## Disposition of former `docs/main_notes.md`

Этот раздел заменяет отдельный файл `docs/main_notes.md`.

### Назначение переноса

- Не держать отдельный файл ради устаревших заметок из `main.py`.
- Зафиксировать решения по каждому пункту в документе текущей итерации.
- Перенести future backlog в `iteration_13`, где он будет частью следующего
  technical/development planning.
- Оставить в `main.py` только ссылку на этот iteration artifact.

### Статусы старых заметок

| Старая заметка | Статус | Решение |
| --- | --- | --- |
| Поиск причины несходимости модели | Deferred | Оставить как часть будущего сравнения current pipeline vs legacy notebook pipeline в `iteration_13`. Без artifact-based сравнения это снова станет разовым debug. |
| Вынести порог корреляции в настройки модели и grid params | Partially done | `correlation_threshold` уже приходит через `filter_params`, а grid строится из `model.filters` / `model.correlation_params`. Оставить follow-up: проверить семантику `correlation_threshold`, `threshold` и `decision_threshold` в модельном research-срезе. |
| `threshold = 0.3` | Partially done | Значение больше не должно жить как безымянная заметка. В коде есть default `correlation_threshold=0.3`, но рабочее значение должно идти из model/grid config. Проверить в future model research. |
| Условия по `Normalized_sell_amount` / `Normalized_buy_amount` | Partially done | Эти признаки и проверки покрыты кодом корреляции и smoke-тестом нормализации buy/sell amounts. Дальше это не docs cleanup, а исследование качества признаков. |
| Страница с аналитикой по моделям | Deferred | В проекте есть Flask/Plotly parquet viewer, но не полноценная model analytics page. Перенести в future analytics/product backlog после решения public/private boundary. |
| Доступ к аналитике по ссылке/доступу к проекту | Deferred | Не делать до решения безопасности, secrets, private data и public/private boundary. Связать с `iteration_13`. |
| Вынести расчет корреляции в отдельный модуль | Partially done | Расчет вынесен в функции `data_operations.py`, но сам файл остается крупным mixed data/model module. Дальнейший перенос делать только после pipeline comparison / artifact strategy. |
| Добавить модуль фиксации структуры БД и индексов + дата последнего `ANALYZE`/`VACUUM` | Partially done | DB schema/index contract уже есть в `settings/db_contracts.py`, smoke checks и `docs/maintenance_guidelines.md`. Отдельной фиксации даты последнего `ANALYZE`/`VACUUM` пока нет; оставить как future maintenance metadata. |
| Улучшить документацию | Done / ongoing | Закрыто итерациями 7-11 как процесс: `AGENTS.md`, skills, README, iteration docs. Продолжать через README impact check. |
| Изучить корреляцию типов кошельков и импакта в пики | Deferred | Оставить как research topic рядом с actor/wallet-level aggregation в `iteration_13`. |
| Продумать стратегию хранения исторических данных и очистку старых логов | Deferred | Связать с data retention, artifact retention и future runtime/ops policy. Не решать в docs cleanup. |
| Продумать глобальные SQL-адаптеры для `np.int32`/`np.int64` | Mostly done | `sqlite3.register_adapter(...)` уже есть в parser/db path. Оставить как future cleanup только если появится drift между SQLite модулями. |
| Рассмотреть отдельный модуль/слой для взаимодействия с БД | Deferred | Частично есть `settings/db_contracts.py`, `modules/sql_funcs/*` и runtime preflight. Полноценный data access layer относится к future data architecture. |
| Функция старта через флаги | Obsolete | Заменено CLI parsing и runtime commands: `main-pipeline`, `param-grid`, `--start_parser`, `test downloaded-from-btc-data`. |
| Старый flag-block `PARSER_TEST`, `MAIN_TEST`, `MOVE_TXS` и т.д. | Historical | Не является инструкцией запуска. Исторический контекст по old runtime scenarios зафиксирован в `iteration_13`. |
| `subcommands` для `argparse --help` | Done | Реализовано в `cli_args.py`; README показывает текущие runtime commands. |

### Deferred backlog moved forward

Эти пункты не выполняются в iteration 11. Они сохранены как будущие направления
в `docs/iterations/iteration_13.md`.

Model and feature research:

- проверить причину несходимости модели через воспроизводимое сравнение current
  pipeline и legacy notebook pipeline;
- проверить, какие параметры должны быть частью grid:
  `correlation_threshold`, `threshold`, `decision_threshold`, параметры
  затухания cumulative features;
- проверить качество признаков вокруг `Normalized_sell_amount`,
  `Normalized_buy_amount`, weighted correlations, wallet/actor-level features
  и реакции на price peaks;
- не добавлять новые feature assumptions без artifact-based проверки и
  маленького reproducible dataset/mock.

Analytics and access:

- решить, остается ли текущий Flask/Plotly parquet viewer внутренним debug tool
  или должен стать model analytics dashboard;
- если делать dashboard, отдельно решить, где хранить training/profit-test
  DataFrames, какие данные можно показывать и как не раскрывать private
  strategy/data;
- доступ "по ссылке" рассматривать только после public/private boundary и
  security review.

Data, SQLite, and maintenance:

- любые изменения вокруг больших SQLite таблиц, `data_table`, индексов,
  `ANALYZE`, `VACUUM`, bulk `INSERT`/`DELETE`/`UPDATE`, `wallet_stats` или
  service tables требуют `$data-pipeline-safety-check`;
- future topics: `data_table + wallet_stats`, `wallet_stats_rebuild_queue`,
  maintenance metadata, data retention, cleanup старых runtime artifacts/logs,
  возможный DB access layer.

Parser and runtime notes:

- ZMQ-настройки сохранены как future parser-runtime research:
  `zmqpubrawblock=tcp://127.0.0.1:28334`,
  `zmqpubrawtx=tcp://127.0.0.1:28335`;
- ZMQ-flow не внедряется до решения parser lifecycle policy и runtime contract.

### Historical implemented capabilities

Этот блок не является backlog. Он сохраняет контекст уже существующего
функционала после удаления `docs/main_notes.md`.

- CLI/runtime entrypoint:
  - `main.py`;
  - `cli_args.py`;
  - `runtime_scenarios.py`.
- Runtime commands:
  - `main-pipeline`;
  - `param-grid`;
  - `--start_parser`;
  - `test downloaded-from-btc-data`.
- Settings/config layer:
  - `settings/runtime.py`;
  - `settings/paths.py`;
  - `settings/runtime_contracts.py`;
  - module-specific settings under `settings/`.
- Logging and agent artifacts:
  - `logs/<run_id>.log`;
  - `logs/agent_runs/<run_id>/manifest.json`;
  - `logs/agent_runs/<run_id>/events.jsonl`;
  - `logs/agent_runs/<run_id>/summary.json`.
- Tests and CI:
  - `tests/unit_smoke`;
  - `tests/integration_live`;
  - `.github/workflows/quality-gate.yml`.
- Data/model features already present:
  - correlation calculation functions;
  - normalized buy/sell amount features;
  - grid parameter generation;
  - deterministic sampling and experiment metadata;
  - Flask/Plotly parquet viewer.
- Historical physical split `data_table -> few_tx_wallets` is archived in
  `docs/experiments/moving_txs_physical_split/` and should not be restored as a
  normal CLI path without a new design review.

### Related files after deletion

- `README.md`
- `README.ru.md`
- `AGENTS.md`
- `docs/junior_plus_program.md`
- `docs/maintenance_guidelines.md`
- `docs/iterations/iteration_13.md`
- `main.py`
- `cli_args.py`
- `runtime_scenarios.py`
- `settings/db_contracts.py`
- `settings/runtime_contracts.py`

## Короткая теория перед практикой

Docs hygiene - это не "сделать текст красивым". Для инженерного проекта важнее
три свойства:

- **актуальность**: читатель понимает, что сейчас правда, а что осталось как
  историческая заметка;
- **проверяемость**: важные утверждения можно связать с файлом, командой,
  тестом, итерацией или decision record;
- **навигация**: документы помогают выбрать следующий файл или действие, а не
  заставляют читать весь репозиторий подряд.

Для этого заметки лучше вести как маленькие decision/status records:
цель, контекст, решение, статус, next step.

## Итог

Выбранный подход: `Medium docs pass` с удалением отдельного `docs/main_notes.md`.

Что сделано:

- Бывший `docs/main_notes.md` разобран по пунктам.
- По каждому старому пункту зафиксирован статус:
  `Done`, `Partially done`, `Mostly done`, `Deferred`, `Obsolete`,
  `Historical`.
- Решения и historical context перенесены в этот документ, чтобы история
  ревизии жила в iteration artifact, а не в отдельной рабочей заметке.
- Future backlog перенесен в `docs/iterations/iteration_13.md`:
  - model and feature research;
  - analytics and access;
  - data retention and DB tooling;
  - parser/ZMQ notes.
- `docs/main_notes.md` удален как дублирующий промежуточный документ.
- `main.py` обновлен: docstring теперь указывает на
  `docs/iterations/iteration_11.md`.

## README impact

None.

Причина: итерация не меняла публичные команды запуска, runtime scenarios,
env/config requirements, структуру логов/artifacts, tests/CI, архитектурное
описание README или known limits. Изменение касается внутренней docs hygiene и
переноса старых заметок в iteration docs.

## Проверки

- `git diff --check` -> pass.
- `python -m py_compile main.py` -> pass.
- `python -m pytest tests\unit_smoke -q` не запускался: runtime behavior не
  менялся, затронут только docstring в `main.py` и документация.

## Industry note (de-facto alternatives)

- Выбранный подход в итерации: удалить отдельный scratch/backlog файл после
  triage и перенести решения в iteration artifact.
- Альтернатива (de-facto): вести отдельный `docs/backlog.md` или issue tracker
  с метками `done`, `deferred`, `obsolete`.
- Почему не берем сейчас: backlog пока небольшой и тесно связан с учебной
  итерацией; отдельный backlog-файл снова стал бы дублировать roadmap и
  iteration 13.
- Мини-пример:
  ```text
  docs/iterations/iteration_11.md - disposition record
  docs/iterations/iteration_13.md - future development backlog
  ```

## Definition of Done

- [x] Проведена ревизия бывшего `docs/main_notes.md` и связанных docs.
- [x] Для актуальных заметок есть понятный статус.
- [x] Устаревшие записи удалены, перенесены или явно помечены как historical.
- [x] Важные заметки связаны с кодом, README, runtime scenarios, checks или
      iteration docs.
- [x] Зафиксированы next steps без реализации задач вне scope.
- [x] Добавлен `Industry note (de-facto alternatives)`.
- [x] Выполнен README impact check.
- [x] Прогнана релевантная проверка или явно указано, почему проверки не
      нужны для docs-only изменения.
