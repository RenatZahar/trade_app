# `main.py` notes and backlog

Этот файл хранит заметки, которые раньше находились комментариями в `main.py`.

## Зачем вынесено из `main.py`

- сохранить `main.py` как исполняемый entrypoint без длинных блоков комментариев;
- держать планы, идеи и диагностику отдельно от runtime-кода;
- упростить поддержку и ревью.


## Backlog до работы с агентом
- Поиск причины несходимости модели (в т.ч. консультация с ментором).
- Вынести порог корреляции в настройки модели и в grid params.
  - `threshold = 0.3`
  - условия по корреляциям `Normalized_sell_amount` / `Normalized_buy_amount`.
- Страница с аналитикой по моделям (вопрос хранения обучающего DataFrame).
- Доступ к аналитике по ссылке/доступу к проекту.
- Вынести расчет корреляции в отдельный модуль.
- Добавить модуль фиксации структуры БД и индексов + дата последнего analyze/vacuum.
- Улучшить документацию.
- Изучить корреляцию типов кошельков и импакта в пики для ускорения расчетов.
- Продумать стратегию хранения исторических данных и очистку старых логов.
- Продумать глобальные SQL-адаптеры (например, для `np.int32`/`np.int64`).
- Рассмотреть отдельный модуль/слой для взаимодействия с БД.


## Backlog после старта работы с агентом
- функция старта через флаги?
--
    PARSER_TEST = 0
    FLASK_TEST = 0
    MAIN_TEST = 0
    TEACHING_TEST = 0 # 1 or 0.1
    TESTS_FROM_MODULES = 0
    PARAM_GRID_TESTING = 0
    MOVE_TXS = 0

    if TESTS_FROM_MODULES:
        converge_of_elasticnet()

    if MOVE_TXS:
        moving_txs()

    if MAIN_TEST:
        mf.start_flask()
        mf.start_btc_price_updater()
        update_peaks()
        mf.teach_and_update_models(TEACHING_TEST)

    if PARAM_GRID_TESTING:
        mf.test_param_grid(TEACHING_TEST)

    raise SystemExit(0)
- subcommands для argparse --help

## Выполнено (исторические заметки)

- Добавлен `data_operations.py` в `.gitignore`.
- Оптимизирован сбор данных для обучения (в т.ч. чистка БД от кошельков с 1–2 txs).
- Добавлен модуль визуализации plotly + flask.
- Добавлен базовый способ расчета корреляции.
- Добавлено обучение по grid-параметрам.
- Выполнен рефакторинг и упрощение логики.

## Технические заметки

- Правило для больших SQLite/maintenance-задач:
  - перед рискованными bulk-операциями сначала делать короткий design review альтернатив;
  - явно оценивать full scan, `GROUP BY`, массовые `DELETE` / `INSERT` / `UPDATE`, пересоздание индексов и риск прерывания;
  - подробности зафиксированы в `docs/maintenance_guidelines.md`.
- Идея: фильтровать кошельки средствами SQLite до разбиения на чанки.
- Идея: протестировать разные `decision_threshold` для покупок/продаж после подготовки кода под mock-данные.
- Индексы (историческая фиксация):
  - `(0, 'idx_block_height', 0, 'c', 0)`
  - `(1, 'idx_wallet_id', 0, 'c', 0)`
- ZMQ-заметки (на будущее):
  - `zmqpubrawblock=tcp://127.0.0.1:28334`
  - `zmqpubrawtx=tcp://127.0.0.1:28335`
  - `zmqpubrawblock` отправляет полные данные о новых блоках;
  - `zmqpubrawtx` отправляет полные данные о новых транзакциях.

## Связанные файлы

- `main.py`
- `docs/junior_plus_program.md`
- `docs/maintenance_guidelines.md`
