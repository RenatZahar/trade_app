# moving_txs.py

import sqlite3
import traceback
import time
import sys
import re
from datetime import datetime
from pathlib import Path
from settings.paths import BLOCKS_SQL_DATA
from settings.sql import LOW_TX_WALLET_MAX_TX_COUNT, SQL_LIMIT_BATCH_SIZE, SQL_RETURN_BATCH_SIZE

import logging
logger = logging.getLogger("app")

SETTINGS_SQL_PATH = Path(__file__).resolve().parents[2] / "settings" / "sql.py"

try:
    from modules.logger.run_tracker import get_current_run_tracker
    from modules.logger import logger as app_logger_module
except Exception:  # pragma: no cover - fallback for ad-hoc standalone execution
    get_current_run_tracker = None
    app_logger_module = None


def apply_maintenance_pragmas(cursor):
    """
    Безопасный набор PRAGMA для ускорения bulk-операций без ухода в aggressive-режим.
    """
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA temp_store=MEMORY;")
    cursor.execute("PRAGMA cache_size=-200000;")


def apply_large_scan_pragmas(cursor):
    """
    PRAGMA для больших GROUP BY/JOIN по сотням миллионов строк.
    temp_store=FILE принципиален: иначе SQLite может держать огромные временные
    B-tree/сортировки в RAM и довести Windows до активного swap/pagefile.
    """
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA temp_store=FILE;")
    cursor.execute("PRAGMA cache_size=-100000;")


def format_seconds_human(total_seconds):
    total_seconds = max(0, int(total_seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def get_tracker_or_none():
    if get_current_run_tracker is None:
        return None
    try:
        return get_current_run_tracker()
    except RuntimeError:
        return None


class ProgressReporter:
    def __init__(self, total_items, step_name, percent_step=2.0):
        self.total_items = max(int(total_items or 0), 0)
        self.step_name = step_name
        self.percent_step = percent_step
        self.next_progress_pct = percent_step
        self.started_at = time.perf_counter()
        self.tracker = get_tracker_or_none()

    def emit(self, processed_items):
        if self.total_items <= 0:
            return

        processed_items = min(int(processed_items), self.total_items)
        progress_pct = (processed_items / self.total_items) * 100
        should_emit = (
            progress_pct >= self.next_progress_pct
            or processed_items >= self.total_items
        )
        if not should_emit:
            return

        elapsed_sec = max(time.perf_counter() - self.started_at, 1e-9)
        speed_items_per_sec = processed_items / elapsed_sec
        remaining_items = max(self.total_items - processed_items, 0)
        eta_sec = int(remaining_items / speed_items_per_sec) if speed_items_per_sec > 0 else None
        details = (
            f"step={self.step_name} "
            f"processed_items={processed_items} "
            f"total_items={self.total_items} "
            f"progress_pct={progress_pct:.2f} "
            f"speed_items_per_sec={speed_items_per_sec:.2f} "
            f"eta_sec={eta_sec} "
            f"eta_human={format_seconds_human(eta_sec or 0)}"
        )

        logger.info(details)
        if self.tracker is not None and app_logger_module is not None and self.tracker.current_stage:
            app_logger_module.log_tracker_stage_progress(self.tracker, details)

        while progress_pct >= self.next_progress_pct:
            self.next_progress_pct += self.percent_step

def list_tables(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
          AND name IN ('data_table', 'few_tx_wallets');
        """
    )
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return tables

def check_db_structures(db_path):
    """
    Быстрая проверка совместимости рабочих таблиц без сканирования всех данных.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        if not check_table_structures(conn, 'few_tx_wallets', 'data_table'):
            raise RuntimeError("Структуры таблиц не совпадают!")
    except Exception as e:
        logger.error(f"Ошибка при проверке структуры БД: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def check_db(db_path):
    """
    Тяжелая сервисная очистка: проверяет структуру и удаляет полные дубли из data_table.
    Не вызывать внутри штатного move_txs: на сотнях миллионов строк GROUP BY по всем
    колонкам занимает очень много времени.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # 1) проверяем структуру таблиц
        if not check_table_structures(conn, 'few_tx_wallets', 'data_table'):
            raise RuntimeError("Структуры таблиц не совпадают!")

        # 2) удаляем полные дубликаты строк из data_table
        #    — оставляем только одну строку для каждой комбинации значений во всех столбцах
        cursor.execute("PRAGMA table_info(data_table);")
        cols = [r[1] for r in cursor.fetchall()]
        if not cols:
            raise RuntimeError("data_table не содержит столбцов")

        #комментарий: строим GROUP BY по всем колонкам (кавычки на случай спец.символов)
        group_by = ", ".join(['"{}"'.format(c) for c in cols])

        #комментарий: удаляем все дубликаты, оставляя строку с минимальным rowid для каждой полной комбинации значений
        sql = (
            "DELETE FROM {tbl} "
            "WHERE rowid NOT IN ("
            "  SELECT MIN(rowid) FROM {tbl} "
            "  GROUP BY {grp}"
            ");"
        ).format(tbl="data_table", grp=group_by)

        cursor.execute(sql)
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка при проверке и очистке БД: {e}")
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()

def get_table_columns(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [(col[1], normalize_sqlite_type(col[2])) for col in cursor.fetchall()]
    cursor.close()
    return columns

def normalize_sqlite_type(type_name):
    # Оставляем только логически значимые типы
    t = type_name.strip().upper()
    if t in ("INT", "INTEGER", "INT4", "INT8"):
        return "INTEGER"
    if t in ("REAL", "FLOAT", "DOUBLE"):
        return "REAL"
    if t == "TEXT":
        return "TEXT"
    return t

def check_table_structures(conn, table1, table2):
    cols1 = get_table_columns(conn, table1)
    cols2 = get_table_columns(conn, table2)
    # print(cols1)
    # print(cols2)
    if cols1 != cols2:
        logger.warning("ВНИМАНИЕ! Структуры таблиц не совпадают!")
        logger.warning(f"{table1}: {cols1}")
        logger.warning(f"{table2}: {cols2}")
        return False
    logger.info("Структуры таблиц совпадают.")
    return True

def get_unique_indices(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA index_list({table_name});")
    # [('0', 'sqlite_autoindex_data_table_1', 1, ...), ...]
    unique_indices = [row[1] for row in cursor.fetchall() if row[2]]
    cursor.close()
    return unique_indices


def drop_data_table_indexes(db_path):
    """
    Историческая функция для агрессивных bulk-сценариев.
    В штатном move_txs больше не используется: индекс Wallet_id нужен для больших
    GROUP BY/JOIN, а финальное состояние БД должно сохранять рабочие индексы.
    """
    logger.info('start drop_data_table_indexes')
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='index'
              AND tbl_name='data_table'
              AND sql IS NOT NULL;
            """
        )
        index_names = [row[0] for row in cursor.fetchall()]
        for index_name in index_names:
            cursor.execute(f"DROP INDEX IF EXISTS {index_name};")
        conn.commit()
        logger.info(f"Индексы data_table удалены: {index_names}")
    except Exception as e:
        logger.error(f"Ошибка при удалении индексов data_table: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def create_wallet_id_index(db_path):
    """
    Создает только индекс Wallet_id, который нужен для GROUP BY/JOIN в move_txs.
    Остальные рабочие индексы создаются уже после rebuild/swap.
    """
    logger.info('start create_wallet_id_index')
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='data_table';"
        )
        if not cursor.fetchone():
            logger.info("Таблица data_table не найдена. Пропускаем idx_wallet_id.")
            return
        cursor.execute("PRAGMA table_info(data_table);")
        cols = [col[1] for col in cursor.fetchall()]
        if 'Wallet_id' in cols:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_wallet_id ON data_table (Wallet_id);"
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка при создании idx_wallet_id: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def return_few_tx_wallets_to_data_table(db_path,
                                        source_table='few_tx_wallets',
                                        target_table='data_table',
                                        batch_size=SQL_RETURN_BATCH_SIZE):
    """
    Пакетно переносит строки из source_table в target_table на стороне SQLite
    и удаляет их из source_table.

    Алгоритм:
    - выбираем батч rowid во временную temp-таблицу;
    - делаем INSERT INTO ... SELECT ... внутри SQLite;
    - удаляем тот же батч из source_table;
    - фиксируем транзакцию по батчу, чтобы прогон был возобновляемым после остановки.
    """
    logger.info('start return_few_tx_wallets_to_data_table (sql-to-sql batches)')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        apply_maintenance_pragmas(cursor)
        total_rows = get_count_in_table(db_path, table_name=source_table) or 0
        processed_rows = 0
        progress_reporter = ProgressReporter(
            total_items=total_rows,
            step_name=f"{source_table}_to_{target_table}",
            percent_step=2.0,
        )

        # Получаем список столбцов для INSERT
        cursor.execute("PRAGMA table_info({});".format(source_table))
        cols = [col[1] for col in cursor.fetchall()]

        col_list = ", ".join(cols)
        insert_sql = (
            "INSERT INTO {tgt} ({cols}) "
            "SELECT {cols} FROM {src} "
            "WHERE rowid IN (SELECT source_rowid FROM temp_return_rowids);"
        ).format(tgt=target_table, cols=col_list, src=source_table)
        delete_sql = (
            "DELETE FROM {src} "
            "WHERE rowid IN (SELECT source_rowid FROM temp_return_rowids);"
        ).format(src=source_table)

        cursor.execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS temp_return_rowids (
                source_rowid INTEGER PRIMARY KEY
            );
            """
        )
        conn.commit()
        
        logger.info("Старт переноса")
        while True:
            cursor.execute("BEGIN;")
            cursor.execute("DELETE FROM temp_return_rowids;")
            cursor.execute(
                """
                INSERT INTO temp_return_rowids (source_rowid)
                SELECT rowid
                FROM {src}
                LIMIT ?;
                """.format(src=source_table),
                (batch_size,)
            )

            cursor.execute("SELECT COUNT(*) FROM temp_return_rowids;")
            batch_count = cursor.fetchone()[0]
            if not batch_count:
                conn.commit()
                break

            cursor.execute(insert_sql)
            cursor.execute(delete_sql)
            conn.commit()
            processed_rows += batch_count
            logger.info("Перенесено {} строк".format(batch_count))
            progress_reporter.emit(processed_rows)

        logger.info("Все данные успешно перемещены из {} в {}.".format(source_table, target_table))
        if source_table == 'few_tx_wallets' and target_table == 'data_table':
            set_txs_moved_state(False)

    except Exception as e:
        logger.error("Ошибка при возврате данных: {}".format(e))
        conn.rollback()
        raise
    finally:
        try:
            cursor.execute("DROP TABLE IF EXISTS temp_return_rowids;")
            conn.commit()
        except Exception:
            pass
        cursor.close()
        conn.close()

def get_count_in_table(db_path, table_name='temp_wallets'):
    logger.info('start get_count_in_table')
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # #comment: Выполнение запроса для получения количества записей
        cursor.execute("SELECT COUNT(*) FROM {tbl};".format(tbl=table_name))
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception as e:
        logger.error(f"Ошибка при подсчёте записей в таблице {table_name}: {e}")
        return None

def create_target_table(db_path, target_table='few_tx_wallets', source_table='data_table'):
    """
    1. Создает новую таблицу (например, few_tx_wallets) с такой же схемой, как у исходной таблицы (data_table).
    """
    logger.info('start create_target_table')
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # #comment: создание целевой таблицы по схеме исходной таблицы (без данных)
        sql = (
            "CREATE TABLE IF NOT EXISTS {tgt} "
            "AS SELECT * FROM {src} WHERE 0;"
        ).format(tgt=target_table, src=source_table)
        cursor.execute(sql)
        conn.commit()
        logger.info(f"Таблица {target_table} создана или уже существует.")
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы {target_table}: {e}")
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def quote_identifier(identifier):
    return '"{}"'.format(str(identifier).replace('"', '""'))


def get_table_column_names(conn, table_name):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info({});".format(quote_identifier(table_name)))
    columns = [col[1] for col in cursor.fetchall()]
    cursor.close()
    if not columns:
        raise RuntimeError("Таблица {} не содержит столбцов".format(table_name))
    return columns


def set_txs_moved_state(is_moved):
    """
    Фиксирует состояние разнесения таблиц в settings/sql.py после успешного сценария.
    """
    value = "True" if is_moved else "False"
    text = SETTINGS_SQL_PATH.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r"^TXS_MOVED\s*=\s*(True|False)\b",
        f"TXS_MOVED = {value}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise RuntimeError("Не удалось обновить TXS_MOVED в settings/sql.py")
    if new_text != text:
        SETTINGS_SQL_PATH.write_text(new_text, encoding="utf-8")
        logger.info("TXS_MOVED обновлен: %s", value)


def create_wallet_targets_table(db_path,
                                txs_count,
                                targets_table='service_wallet_targets',
                                data_table='data_table',
                                storage_table='few_tx_wallets'):
    """
    Собирает целевое размещение кошельков по обеим таблицам.
    Кошельки с общим количеством строк <= txs_count должны лежать в storage_table,
    остальные - в data_table.
    """
    logger.info('start create_wallet_targets_table')
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        apply_large_scan_pragmas(cursor)

        cursor.execute("DROP TABLE IF EXISTS {};".format(quote_identifier(targets_table)))
        cursor.execute(
            """
            CREATE TABLE {targets} (
                wallet_id PRIMARY KEY,
                target_table TEXT NOT NULL,
                rows_count INTEGER NOT NULL
            );
            """.format(targets=quote_identifier(targets_table))
        )

        sql = """
            INSERT INTO {targets} (wallet_id, target_table, rows_count)
            SELECT
                Wallet_id,
                CASE
                    WHEN SUM(cnt) <= ? THEN ?
                    ELSE ?
                END AS target_table,
                SUM(cnt) AS rows_count
            FROM (
                SELECT Wallet_id, COUNT(*) AS cnt
                FROM {data_table}
                WHERE Wallet_id IS NOT NULL
                GROUP BY Wallet_id

                UNION ALL

                SELECT Wallet_id, COUNT(*) AS cnt
                FROM {storage_table}
                WHERE Wallet_id IS NOT NULL
                GROUP BY Wallet_id
            ) AS wallet_counts
            GROUP BY Wallet_id;
        """.format(
            targets=quote_identifier(targets_table),
            data_table=quote_identifier(data_table),
            storage_table=quote_identifier(storage_table),
        )
        cursor.execute(sql, (txs_count, storage_table, data_table))
        conn.commit()
        logger.info(
            "Целевая таблица кошельков {} создана. Порог <= {} строк.".format(
                targets_table,
                txs_count,
            )
        )
    except Exception as e:
        logger.error("Ошибка при создании целевого списка кошельков: {}".format(e))
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def create_move_rowids_table(db_path,
                             source_table,
                             target_table,
                             targets_table='service_wallet_targets',
                             rowids_table='service_move_rowids'):
    """
    Готовит rowid строк, которые лежат не в своей целевой таблице.
    Это позволяет использовать индексы Wallet_id на этапе поиска, а затем удалить индексы
    перед тяжелым DELETE из data_table.
    """
    logger.info(
        "start create_move_rowids_table source=%s target=%s rowids_table=%s",
        source_table,
        target_table,
        rowids_table,
    )
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        apply_large_scan_pragmas(cursor)

        cursor.execute("DROP TABLE IF EXISTS {};".format(quote_identifier(rowids_table)))
        cursor.execute(
            """
            CREATE TABLE {rowids} (
                source_rowid INTEGER PRIMARY KEY
            );
            """.format(rowids=quote_identifier(rowids_table))
        )

        sql = """
            INSERT INTO {rowids} (source_rowid)
            SELECT src.rowid
            FROM {source} AS src
            JOIN {targets} AS tgt
              ON tgt.wallet_id = src.Wallet_id
            WHERE tgt.target_table = ?;
        """.format(
            rowids=quote_identifier(rowids_table),
            source=quote_identifier(source_table),
            targets=quote_identifier(targets_table),
        )
        cursor.execute(sql, (target_table,))
        inserted_rows = cursor.rowcount
        conn.commit()
        logger.info(
            "Подготовлено rowid для переноса %s -> %s: %s",
            source_table,
            target_table,
            inserted_rows,
        )
    except Exception as e:
        logger.error("Ошибка при подготовке rowid для переноса: {}".format(e))
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def move_prepared_rows(db_path,
                       source_table,
                       target_table,
                       rowids_table='service_move_rowids',
                       batch_size=SQL_RETURN_BATCH_SIZE):
    """
    Переносит заранее подготовленные rowid из source_table в target_table батчами.
    Каждый батч атомарен: INSERT, DELETE из source и удаление обработанных rowid
    коммитятся вместе.
    """
    logger.info(
        "start move_prepared_rows source=%s target=%s rowids_table=%s",
        source_table,
        target_table,
        rowids_table,
    )
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        apply_large_scan_pragmas(cursor)
        cursor.execute("SELECT COUNT(*) FROM {};".format(quote_identifier(rowids_table)))
        total_rows = cursor.fetchone()[0]
        processed_rows = 0
        progress_reporter = ProgressReporter(
            total_items=total_rows,
            step_name="{}_to_{}".format(source_table, target_table),
            percent_step=2.0,
        )

        columns = get_table_column_names(conn, source_table)
        column_list = ", ".join(quote_identifier(col) for col in columns)

        insert_sql = """
            INSERT INTO {target} ({columns})
            SELECT {columns}
            FROM {source}
            WHERE rowid IN (SELECT source_rowid FROM temp_move_rowids);
        """.format(
            target=quote_identifier(target_table),
            columns=column_list,
            source=quote_identifier(source_table),
        )
        delete_source_sql = """
            DELETE FROM {source}
            WHERE rowid IN (SELECT source_rowid FROM temp_move_rowids);
        """.format(source=quote_identifier(source_table))
        delete_rowids_sql = """
            DELETE FROM {rowids}
            WHERE source_rowid IN (SELECT source_rowid FROM temp_move_rowids);
        """.format(rowids=quote_identifier(rowids_table))

        cursor.execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS temp_move_rowids (
                source_rowid INTEGER PRIMARY KEY
            );
            """
        )
        conn.commit()

        while True:
            cursor.execute("BEGIN;")
            cursor.execute("DELETE FROM temp_move_rowids;")
            cursor.execute(
                """
                INSERT INTO temp_move_rowids (source_rowid)
                SELECT source_rowid
                FROM {rowids}
                LIMIT ?;
                """.format(rowids=quote_identifier(rowids_table)),
                (batch_size,),
            )
            cursor.execute("SELECT COUNT(*) FROM temp_move_rowids;")
            batch_count = cursor.fetchone()[0]
            if not batch_count:
                conn.commit()
                break

            cursor.execute(insert_sql)
            cursor.execute(delete_source_sql)
            cursor.execute(delete_rowids_sql)
            conn.commit()

            processed_rows += batch_count
            progress_reporter.emit(processed_rows)

        logger.info(
            "Перенос %s -> %s завершен. Перенесено строк: %s",
            source_table,
            target_table,
            processed_rows,
        )
    except Exception as e:
        logger.error("Ошибка при переносе подготовленных строк: {}".format(e))
        conn.rollback()
        raise
    finally:
        try:
            cursor.execute("DROP TABLE IF EXISTS temp_move_rowids;")
            conn.commit()
        except Exception:
            pass
        cursor.close()
        conn.close()


def create_rebuild_tables(db_path,
                          rebuild_data_table='service_rebuild_data_table',
                          rebuild_storage_table='service_rebuild_few_tx_wallets',
                          source_table='data_table'):
    """
    Создает пустые rebuild-таблицы по схеме data_table.
    До swap исходные data_table/few_tx_wallets остаются рабочими и не изменяются.
    """
    logger.info(
        "start create_rebuild_tables data=%s storage=%s",
        rebuild_data_table,
        rebuild_storage_table,
    )
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        apply_large_scan_pragmas(cursor)

        for table_name in (rebuild_data_table, rebuild_storage_table):
            cursor.execute("DROP TABLE IF EXISTS {};".format(quote_identifier(table_name)))
            cursor.execute(
                """
                CREATE TABLE {target}
                AS SELECT *
                FROM {source}
                WHERE 0;
                """.format(
                    target=quote_identifier(table_name),
                    source=quote_identifier(source_table),
                )
            )
        conn.commit()
        logger.info("Rebuild-таблицы созданы.")
    except Exception as e:
        logger.error("Ошибка при создании rebuild-таблиц: {}".format(e))
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def populate_rebuild_table(db_path,
                           rebuild_table,
                           target_table_name,
                           targets_table='service_wallet_targets',
                           data_table='data_table',
                           storage_table='few_tx_wallets'):
    """
    Наполняет одну rebuild-таблицу строками из обеих исходных таблиц по целевому
    размещению кошельков. Строки с Wallet_id NULL сохраняются в исходной стороне:
    NULL из data_table остается в data_table, NULL из few_tx_wallets остается в few_tx_wallets.
    """
    logger.info(
        "start populate_rebuild_table rebuild_table=%s target_table_name=%s",
        rebuild_table,
        target_table_name,
    )
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        apply_large_scan_pragmas(cursor)

        columns = get_table_column_names(conn, data_table)
        column_list = ", ".join(quote_identifier(col) for col in columns)
        source_column_list = ", ".join("src.{}".format(quote_identifier(col)) for col in columns)
        inserted_rows = 0

        for source_table in (data_table, storage_table):
            sql = """
                INSERT INTO {rebuild} ({columns})
                SELECT {source_columns}
                FROM {source} AS src
                JOIN {targets} AS tgt
                  ON tgt.wallet_id = src.Wallet_id
                WHERE tgt.target_table = ?;
            """.format(
                rebuild=quote_identifier(rebuild_table),
                columns=column_list,
                source_columns=source_column_list,
                source=quote_identifier(source_table),
                targets=quote_identifier(targets_table),
            )
            cursor.execute(sql, (target_table_name,))
            inserted_rows += max(cursor.rowcount, 0)

        null_source_table = data_table if target_table_name == data_table else storage_table
        sql = """
            INSERT INTO {rebuild} ({columns})
            SELECT {columns}
            FROM {source}
            WHERE Wallet_id IS NULL;
        """.format(
            rebuild=quote_identifier(rebuild_table),
            columns=column_list,
            source=quote_identifier(null_source_table),
        )
        cursor.execute(sql)
        inserted_rows += max(cursor.rowcount, 0)

        conn.commit()
        logger.info(
            "Rebuild-таблица %s наполнена. Вставлено строк: %s",
            rebuild_table,
            inserted_rows,
        )
        return inserted_rows
    except Exception as e:
        logger.error("Ошибка при наполнении rebuild-таблицы: {}".format(e))
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def swap_rebuild_tables(db_path,
                        rebuild_data_table='service_rebuild_data_table',
                        rebuild_storage_table='service_rebuild_few_tx_wallets',
                        data_table='data_table',
                        storage_table='few_tx_wallets',
                        backup_data_table='service_backup_data_table',
                        backup_storage_table='service_backup_few_tx_wallets'):
    """
    Короткая транзакция swap: старые таблицы переименовываются в backup,
    rebuild-таблицы становятся рабочими таблицами.
    """
    logger.info("start swap_rebuild_tables")
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        apply_large_scan_pragmas(cursor)

        cursor.execute("BEGIN IMMEDIATE;")
        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='index'
              AND tbl_name=?
              AND sql IS NOT NULL;
            """,
            (data_table,)
        )
        data_table_indexes = [row[0] for row in cursor.fetchall()]
        for index_name in data_table_indexes:
            cursor.execute("DROP INDEX IF EXISTS {};".format(quote_identifier(index_name)))
        logger.info("Индексы старой data_table перед swap удалены: %s", data_table_indexes)

        cursor.execute("DROP TABLE IF EXISTS {};".format(quote_identifier(backup_data_table)))
        cursor.execute("DROP TABLE IF EXISTS {};".format(quote_identifier(backup_storage_table)))
        cursor.execute(
            "ALTER TABLE {} RENAME TO {};".format(
                quote_identifier(data_table),
                quote_identifier(backup_data_table),
            )
        )
        cursor.execute(
            "ALTER TABLE {} RENAME TO {};".format(
                quote_identifier(storage_table),
                quote_identifier(backup_storage_table),
            )
        )
        cursor.execute(
            "ALTER TABLE {} RENAME TO {};".format(
                quote_identifier(rebuild_data_table),
                quote_identifier(data_table),
            )
        )
        cursor.execute(
            "ALTER TABLE {} RENAME TO {};".format(
                quote_identifier(rebuild_storage_table),
                quote_identifier(storage_table),
            )
        )
        conn.commit()
        logger.info("Swap rebuild-таблиц завершен.")
    except Exception as e:
        logger.error("Ошибка при swap rebuild-таблиц: {}".format(e))
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def rebuild_wallet_tables(db_path):
    """
    Разносит data_table/few_tx_wallets через пересборку таблиц, без массового DELETE.
    Дорогие операции: два больших INSERT INTO ... SELECT и последующее пересоздание индексов.
    """
    logger.info("start rebuild_wallet_tables")
    create_rebuild_tables(db_path)
    populate_rebuild_table(
        db_path,
        rebuild_table='service_rebuild_data_table',
        target_table_name='data_table',
    )
    populate_rebuild_table(
        db_path,
        rebuild_table='service_rebuild_few_tx_wallets',
        target_table_name='few_tx_wallets',
    )
    swap_rebuild_tables(db_path)


def cleanup_move_txs_service_tables(db_path):
    logger.info('start cleanup_move_txs_service_tables')
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for table_name in (
            'service_wallet_targets',
            'service_move_to_few_rowids',
            'service_move_to_data_rowids',
            'service_rebuild_data_table',
            'service_rebuild_few_tx_wallets',
            'service_backup_data_table',
            'service_backup_few_tx_wallets',
        ):
            cursor.execute("DROP TABLE IF EXISTS {};".format(quote_identifier(table_name)))
        conn.commit()
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        logger.info("Служебные таблицы move_txs удалены.")
    except Exception as e:
        logger.error("Ошибка при очистке служебных таблиц move_txs: {}".format(e))
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def create_temp_wallets_table(db_path, txs_count, source_table='data_table', temp_table='temp_wallets'):
    """
    2. Создает служебную таблицу (temp_wallets) для хранения id кошельков, у которых количество транзакций ≤ txs_count.
       Если таблица уже существует, создание и заполнение пропускается.
    """
    logger.info('start create_temp_wallets_table')
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # #comment: проверка наличия служебной таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (temp_table,))
        if cursor.fetchone():
            logger.info(f"Таблица {temp_table} уже существует. Пропускаем создание и заполнение.")
            return

        # Создаем служебную таблицу temp_wallets
        sql = """
            CREATE TABLE {tmp} (
                wallet_id TEXT PRIMARY KEY
            );
        """.format(tmp=temp_table)
        cursor.execute(sql)
        conn.commit()

        # Заполняем temp_wallets идентификаторами кошельков с количеством транзакций ≤ 2
        sql = (
            "INSERT INTO {tmp} (wallet_id) "
            "SELECT Wallet_id FROM ( "
            "  SELECT Wallet_id, COUNT(*) AS cnt "
            "  FROM {src} "
            "  GROUP BY Wallet_id "
            ") WHERE cnt <= ?;"
            ).format(tmp=temp_table, src=source_table)
        
        cursor.execute(sql, (txs_count,))
        conn.commit()
        logger.info(f"Таблица {temp_table} успешно создана и заполнена.")
    except Exception as e:
        logger.error(f"Ошибка при создании или заполнении таблицы {temp_table}: {e}")
        traceback.print_exc()
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def optimize_db(db_path):
    """
    Включает режим WAL и устанавливает оптимальные параметры для ускорения операций записи.
    """
    logger.info('start optimize_db')
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        apply_large_scan_pragmas(cursor)
        conn.commit()
        logger.info(
            "База данных оптимизирована: WAL, synchronous=NORMAL, temp_store=FILE, cache_size=-100000."
        )
    except Exception as e:
        logger.warning(f"Не удалось оптимизировать БД: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def process_wallets(db_path, source_table='data_table', target_table='few_tx_wallets', 
                    temp_table='temp_wallets', batch_size=SQL_LIMIT_BATCH_SIZE):
    """
    Порционно обрабатывает кошельки из temp_wallets:
    - Выбирает батчи кошельков из temp_wallets.
    - Для каждого батча вызывает process_wallets_batch.
    - Если temp_wallets пуста, таблица удаляется.
    """
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM {tmp};".format(tmp=temp_table))
        total = cursor.fetchone()[0]
        processed = 0
        start_all = time.time()
        progress_reporter = ProgressReporter(
            total_items=total,
            step_name=f"{source_table}_to_{target_table}_wallets",
            percent_step=2.0,
        )

        while True:
            cursor.execute("SELECT wallet_id FROM {tmp} LIMIT ?;".format(tmp=temp_table), (batch_size,))
            wallets = [row[0] for row in cursor.fetchall()]
            if not wallets:
                logger.info(f"Таблица {temp_table} пуста. Удаляем таблицу {temp_table}.")
                cursor.execute("DROP TABLE IF EXISTS {tmp};".format(tmp=temp_table))
                conn.commit()
                break

            process_wallets_batch(db_path,
                                source_table=source_table,
                                target_table=target_table,
                                temp_table=temp_table,
                                wallet_ids=wallets)
            
            processed += len(wallets)
            elapsed = time.time() - start_all
            eta = (elapsed / processed) * (total - processed) / 60
            sys.stdout.write(f'\rProcessed: {processed}/{total}, ETA: {eta:.2f} min')
            sys.stdout.flush()
            progress_reporter.emit(processed)

    except Exception as e:
        logger.error(f"Ошибка при обработке кошельков: {e}")
        traceback.print_exc()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def process_wallets_batch(db_path, source_table='data_table', target_table='few_tx_wallets', 
                          temp_table='temp_wallets', wallet_ids=None):
    """
    Обрабатывает одну порцию кошельков за одну транзакцию:
    - Копирует все строки для указанных кошельков из source_table в target_table.
    - Удаляет скопированные строки из source_table.
    - Удаляет обработанные id кошельков из temp_table.
    """
    logger.info('start process_wallets_batch')

    if not wallet_ids:
        return
    conn = None
    cursor = None
    try:
        start_time = time.time()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in wallet_ids)  # #comment: генерируем строку "?, ?, ... ?"
        
        # Начинаем транзакцию для всей порции
        cursor.execute("BEGIN;")
        
        # Копируем строки из source_table в target_table для всех кошельков из списка
        sql = (
            "INSERT INTO {target} "
            "SELECT * FROM {source} "
            "WHERE Wallet_id IN ({ph});"
        ).format(
            target=target_table,
            source=source_table,
            ph=placeholders
        )
        cursor.execute(sql, wallet_ids)
        
        # Удаляем скопированные строки из source_table
        sql = "DELETE FROM {src} WHERE Wallet_id IN ({ph});".format(
            src=source_table,
            ph=placeholders
        )
        cursor.execute(sql, wallet_ids)
            
        # Удаляем id кошельков из temp_table
        query_delete_temp = "DELETE FROM {tmp} WHERE wallet_id IN ({ph});".format(
            tmp=temp_table, ph=placeholders
            )
        cursor.execute(query_delete_temp, wallet_ids)
        conn.commit()  # #comment: фиксируем транзакцию для всей группы кошельков
        # print(f"Обработана порция из {len(wallet_ids)} кошельков.")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка при обработке порции кошельков {wallet_ids}: {e}")
        traceback.print_exc()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def print_now():
    logger.info(f'Старт в {datetime.now()}')

REQUIRED_DATA_TABLE_INDEXES = {
    "idx_wallet_id",
    "idx_block_height",
    "idx_txs_blocktime",
}


def get_data_table_indexes(db_path):
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='index'
              AND tbl_name='data_table';
            """
        )
        return {row[0] for row in cursor.fetchall()}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def check_required_data_table_indexes(db_path):
    indexes = get_data_table_indexes(db_path)
    missing_indexes = sorted(REQUIRED_DATA_TABLE_INDEXES - indexes)
    if missing_indexes:
        raise RuntimeError(
            "В data_table отсутствуют обязательные индексы: "
            + ", ".join(missing_indexes)
        )
    logger.info(
        "Проверка индексов data_table успешна: %s",
        sorted(REQUIRED_DATA_TABLE_INDEXES),
    )


def warn_required_data_table_indexes(db_path, scenario_name=None):
    try:
        indexes = get_data_table_indexes(db_path)
    except Exception as e:
        logger.warning(
            "Не удалось проверить индексы data_table перед сценарием %s: %s",
            scenario_name or "unknown",
            e,
        )
        return False

    missing_indexes = sorted(REQUIRED_DATA_TABLE_INDEXES - indexes)
    if missing_indexes:
        logger.warning(
            "Перед сценарием %s в data_table отсутствуют индексы: %s. "
            "Сценарий не остановлен автоматически; при необходимости останови его "
            "и пересоздай индексы.",
            scenario_name or "unknown",
            missing_indexes,
        )
        return False

    logger.info(
        "Перед сценарием %s индексы data_table присутствуют: %s",
        scenario_name or "unknown",
        sorted(REQUIRED_DATA_TABLE_INDEXES),
    )
    return True


def create_indexes(db_path):
    # поддерживаем индексы только в рабочей таблице data_table;
    # few_tx_wallets — хранилищная таблица, индексы на ней не требуются.
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        table = "data_table"
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (table,)
        )
        if not cursor.fetchone():
            logger.info("Таблица data_table не найдена. Пропускаем создание индексов.")
            return

        cursor.execute(f"PRAGMA table_info({table});")
        cols = [col[1] for col in cursor.fetchall()]

        if 'Wallet_id' in cols:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_wallet_id ON data_table (Wallet_id);"
            )
        if 'Block_height' in cols:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_block_height ON data_table (Block_height);"
            )
        if 'Block_time' in cols:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_txs_blocktime ON data_table(Block_time);"
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка при создании индексов: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def moving_txs():
    print_now()
    logger.info(
        "Старт move_txs rebuild/swap: целевое состояние кошельков будет собрано по data_table "
        "и few_tx_wallets. Физический перенос строк через DELETE заменен пересборкой таблиц."
    )

    warn_required_data_table_indexes(BLOCKS_SQL_DATA, "service.move_txs")
    create_target_table(BLOCKS_SQL_DATA, target_table="few_tx_wallets", source_table="data_table")  # #коммент: гарантируем наличие хранилищной таблицы
    check_db_structures(BLOCKS_SQL_DATA)                                                            # #коммент: проверяем совместимость схем без тяжелой дедупликации
    optimize_db(BLOCKS_SQL_DATA)                                                                    # #коммент: включаем WAL/synchronous=NORMAL и temp_store=FILE для больших scan
    create_wallet_id_index(BLOCKS_SQL_DATA)                                                         # #коммент: для GROUP BY/JOIN нужен только Wallet_id; остальные индексы строим после swap
    create_wallet_targets_table(BLOCKS_SQL_DATA, LOW_TX_WALLET_MAX_TX_COUNT)                        # #коммент: считаем целевую таблицу кошелька по обеим таблицам
    # ВАЖНО:
    # До swap старые data_table/few_tx_wallets не изменяются, поэтому остановка безопасна:
    # можно удалить service_rebuild_* и запустить сценарий заново. После swap штатный путь
    # восстановления тот же: заново запустить move_txs и довести сценарий до конца.
    rebuild_wallet_tables(BLOCKS_SQL_DATA)                                                            # #коммент: пересобираем обе таблицы SQL-side без массового DELETE из data_table
    create_indexes(BLOCKS_SQL_DATA)                                                                   # #коммент: финальная проверка рабочих индексов data_table
    check_required_data_table_indexes(BLOCKS_SQL_DATA)                                                 # #коммент: явно подтверждаем готовность рабочей таблицы
    cleanup_move_txs_service_tables(BLOCKS_SQL_DATA)                                                   # #коммент: удаляем service/backup-таблицы после успешной проверки
    set_txs_moved_state(True)                                                                          # #коммент: фиксируем, что строки разнесены между data_table и few_tx_wallets

    logger.info("Работа move_txs rebuild/swap завершена. Финальный COUNT(*) по большим таблицам пропущен.")

if __name__ == "__main__":
    moving_txs()
