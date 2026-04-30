# moving_txs.py
#
# LEGACY MAINTENANCE NOTE:
# Текущий подход физически переносит строки между data_table и few_tx_wallets.
# На сотнях миллионов строк это слишком дорогая конструкция. Не удаляем файл,
# пока не реализована новая модель сбора данных через wallet_stats / флаги
# классификации кошельков, но новые оптимизации лучше проектировать вокруг
# фильтрации pipeline-запросов, а не вокруг массового переноса строк.

import sqlite3
import traceback
import time
import re
from datetime import datetime
from pathlib import Path
from settings.paths import BLOCKS_SQL_DATA
from settings.sql import (
    LOW_TX_WALLET_MAX_TX_COUNT,
    SQL_MOVE_TXS_BACK_BATCH_ROWS,
    SQL_MOVE_TXS_BATCH_ROWS,
    SQL_RETURN_BATCH_SIZE,
)

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

def create_wallet_id_index(db_path, table_name='data_table', index_name='idx_wallet_id'):
    """
    Создает индекс Wallet_id для таблицы, участвующей в maintenance-переносе.
    """
    logger.info('start create_wallet_id_index table=%s index=%s', table_name, index_name)
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (table_name,)
        )
        if not cursor.fetchone():
            logger.info("Таблица %s не найдена. Пропускаем индекс Wallet_id.", table_name)
            return
        cursor.execute("PRAGMA table_info({});".format(quote_identifier(table_name)))
        cols = [col[1] for col in cursor.fetchall()]
        if 'Wallet_id' in cols:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS {} ON {} (Wallet_id);".format(
                    quote_identifier(index_name),
                    quote_identifier(table_name),
                )
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка при создании индекса Wallet_id: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def create_wallet_id_indexes_for_move(db_path):
    create_wallet_id_index(db_path, table_name='data_table', index_name='idx_wallet_id')
    create_wallet_id_index(
        db_path,
        table_name='few_tx_wallets',
        index_name='idx_few_tx_wallets_wallet_id',
    )


def drop_non_wallet_data_table_indexes(db_path):
    """
    На массовом DELETE индексы Block_height/Block_time заметно замедляют перенос.
    Wallet_id оставляем, потому что он нужен для выборки и удаления батчей.
    """
    logger.info("start drop_non_wallet_data_table_indexes")
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for index_name in ("idx_block_height", "idx_txs_blocktime"):
            cursor.execute("DROP INDEX IF EXISTS {};".format(quote_identifier(index_name)))
        conn.commit()
        logger.info("Не-Wallet индексы data_table удалены перед bulk-переносом.")
    except Exception as e:
        logger.error("Ошибка при удалении не-Wallet индексов data_table: %s", e)
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def drop_data_table_runtime_indexes(db_path):
    """
    Удаляет рабочие индексы data_table перед массовым INSERT.
    На возврате few_tx_wallets -> data_table они не помогают выборке, но сильно
    увеличивают цену записи. После успешного возврата create_indexes() создаст
    их заново.
    """
    logger.info("start drop_data_table_runtime_indexes")
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for index_name in (
            "idx_wallet_id",
            "idx_block_height",
            "idx_txs_blocktime",
            "idx_block_height_wallet_id",
        ):
            cursor.execute("DROP INDEX IF EXISTS {};".format(quote_identifier(index_name)))
        conn.commit()
        logger.info("Рабочие индексы data_table удалены перед move_txs_back.")
    except Exception as e:
        logger.error("Ошибка при удалении рабочих индексов data_table: %s", e)
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def drop_index_if_exists(db_path, index_name):
    """
    Удаляет один индекс, если он есть. Используется в maintenance-сценариях,
    когда цена поддержки индекса выше пользы от него на текущем этапе.
    """
    logger.info("start drop_index_if_exists index=%s", index_name)
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DROP INDEX IF EXISTS {};".format(quote_identifier(index_name)))
        conn.commit()
        logger.info("Индекс %s удален или отсутствовал.", index_name)
    except Exception as e:
        logger.error("Ошибка при удалении индекса %s: %s", index_name, e)
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
        batch_number = 0
        total_batches = (total_rows + batch_size - 1) // batch_size if batch_size else 0
        progress_reporter = ProgressReporter(
            total_items=total_rows,
            step_name=f"{source_table}_to_{target_table}",
            percent_step=2.0,
        )

        # Получаем список столбцов для INSERT
        cursor.execute("PRAGMA table_info({});".format(quote_identifier(source_table)))
        cols = [col[1] for col in cursor.fetchall()]

        col_list = ", ".join(quote_identifier(col) for col in cols)
        insert_sql = (
            "INSERT INTO {tgt} ({cols}) "
            "SELECT {cols} FROM {src} "
            "WHERE rowid IN (SELECT source_rowid FROM temp_return_rowids);"
        ).format(
            tgt=quote_identifier(target_table),
            cols=col_list,
            src=quote_identifier(source_table),
        )
        delete_sql = (
            "DELETE FROM {src} "
            "WHERE rowid IN (SELECT source_rowid FROM temp_return_rowids);"
        ).format(src=quote_identifier(source_table))

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
            batch_started_at = time.perf_counter()
            cursor.execute("BEGIN;")
            cursor.execute("DELETE FROM temp_return_rowids;")
            cursor.execute(
                """
                INSERT INTO temp_return_rowids (source_rowid)
                SELECT rowid
                FROM {src}
                LIMIT ?;
                """.format(src=quote_identifier(source_table)),
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
            batch_number += 1
            batch_sec = max(time.perf_counter() - batch_started_at, 1e-9)
            remaining_batches = max(total_batches - batch_number, 0)
            eta_by_last_batch = int(remaining_batches * batch_sec)
            logger.info(
                "Батч %s/%s %s -> %s: rows=%s processed=%s total=%s batch_sec=%.2f eta_by_last_batch=%s",
                batch_number,
                total_batches or "?",
                source_table,
                target_table,
                batch_count,
                processed_rows,
                total_rows,
                batch_sec,
                format_seconds_human(eta_by_last_batch),
            )
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


def table_exists(conn, table_name):
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
              AND name=?;
            """,
            (table_name,),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


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


def cleanup_stale_rebuild_tables(db_path):
    """
    Удаляет черновики старого rebuild/swap-подхода.
    Backup-таблицы здесь намеренно не трогаем: если когда-то swap уже произошел,
    удалять backup можно только после явной проверки состояния БД.
    """
    logger.info("start cleanup_stale_rebuild_tables")
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for index_name in (
            'idx_service_wallet_move_plan_batch',
            'idx_service_wallet_move_plan_direction',
        ):
            cursor.execute("DROP INDEX IF EXISTS {};".format(quote_identifier(index_name)))
        for table_name in (
            'temp_wallets',
            'service_wallet_targets',
            'service_move_to_few_rowids',
            'service_move_to_data_rowids',
            'service_rebuild_data_table',
            'service_rebuild_few_tx_wallets',
            'service_wallet_counts_data',
            'service_wallet_counts_storage',
            'service_wallet_move_meta',
        ):
            cursor.execute("DROP TABLE IF EXISTS {};".format(quote_identifier(table_name)))
        conn.commit()
        logger.info("Старые service/rebuild-таблицы очищены.")
    except Exception as e:
        logger.error("Ошибка при очистке старых service/rebuild-таблиц: %s", e)
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def create_wallet_move_plan(db_path,
                            txs_count,
                            plan_table='service_wallet_move_plan',
                            meta_table='service_wallet_move_meta',
                            data_table='data_table',
                            storage_table='few_tx_wallets'):
    """
    Создает возобновляемый план переносов:
    wallet_id + source_table + target_table + rows_count.

    Если plan_table уже существует, считаем, что предыдущий прогон был прерван,
    и продолжаем с оставшихся строк вместо пересчета GROUP BY.
    """
    logger.info("start create_wallet_move_plan")
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        apply_large_scan_pragmas(cursor)

        if table_exists(conn, plan_table):
            logger.info(
                "Найдена существующая %s. Продолжаем без пересчета GROUP BY/SUM по плану.",
                plan_table,
            )
            return

        cursor.execute("BEGIN;")
        cursor.execute("DROP TABLE IF EXISTS {};".format(quote_identifier(meta_table)))
        cursor.execute(
            """
            CREATE TABLE {plan} (
                wallet_id TEXT NOT NULL,
                source_table TEXT NOT NULL,
                target_table TEXT NOT NULL,
                rows_count INTEGER NOT NULL,
                PRIMARY KEY (wallet_id, source_table, target_table)
            );
            """.format(plan=quote_identifier(plan_table))
        )

        cursor.execute("DROP TABLE IF EXISTS service_wallet_counts_data;")
        cursor.execute("DROP TABLE IF EXISTS service_wallet_counts_storage;")
        cursor.execute(
            """
            CREATE TABLE service_wallet_counts_data AS
            SELECT Wallet_id AS wallet_id, COUNT(*) AS rows_count
            FROM {data_table}
            WHERE Wallet_id IS NOT NULL
            GROUP BY Wallet_id;
            """.format(data_table=quote_identifier(data_table))
        )
        cursor.execute(
            """
            CREATE TABLE service_wallet_counts_storage AS
            SELECT Wallet_id AS wallet_id, COUNT(*) AS rows_count
            FROM {storage_table}
            WHERE Wallet_id IS NOT NULL
            GROUP BY Wallet_id;
            """.format(storage_table=quote_identifier(storage_table))
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_service_wallet_counts_data_wallet_id "
            "ON service_wallet_counts_data(wallet_id);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_service_wallet_counts_storage_wallet_id "
            "ON service_wallet_counts_storage(wallet_id);"
        )

        cursor.execute(
            """
            INSERT INTO {plan} (wallet_id, source_table, target_table, rows_count)
            SELECT
                d.wallet_id,
                ?,
                ?,
                d.rows_count
            FROM service_wallet_counts_data AS d
            LEFT JOIN service_wallet_counts_storage AS s
              ON s.wallet_id = d.wallet_id
            WHERE d.rows_count + COALESCE(s.rows_count, 0) <= ?;
            """.format(plan=quote_identifier(plan_table)),
            (data_table, storage_table, txs_count),
        )
        cursor.execute(
            """
            INSERT INTO {plan} (wallet_id, source_table, target_table, rows_count)
            SELECT
                s.wallet_id,
                ?,
                ?,
                s.rows_count
            FROM service_wallet_counts_storage AS s
            LEFT JOIN service_wallet_counts_data AS d
              ON d.wallet_id = s.wallet_id
            WHERE s.rows_count + COALESCE(d.rows_count, 0) > ?;
            """.format(plan=quote_identifier(plan_table)),
            (storage_table, data_table, txs_count),
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_service_wallet_move_plan_direction
            ON {plan} (source_table, target_table);
            """.format(plan=quote_identifier(plan_table))
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_service_wallet_move_plan_batch
            ON {plan} (source_table, target_table, wallet_id, rows_count);
            """.format(plan=quote_identifier(plan_table))
        )
        cursor.execute("DROP TABLE IF EXISTS service_wallet_counts_data;")
        cursor.execute("DROP TABLE IF EXISTS service_wallet_counts_storage;")
        conn.commit()

        cursor.execute("SELECT COUNT(*), COALESCE(SUM(rows_count), 0) FROM {};".format(
            quote_identifier(plan_table)
        ))
        plans_count, rows_count = cursor.fetchone()
        cursor.execute(
            """
            CREATE TABLE {meta} (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            );
            """.format(meta=quote_identifier(meta_table))
        )
        cursor.executemany(
            "INSERT INTO {} (key, value) VALUES (?, ?);".format(quote_identifier(meta_table)),
            [
                ("plans_count", int(plans_count or 0)),
                ("total_rows", int(rows_count or 0)),
                ("remaining_rows", int(rows_count or 0)),
            ],
        )
        conn.commit()
        logger.info(
            "План переносов создан: направлений=%s, строк_к_переносу=%s, порог <= %s.",
            plans_count,
            rows_count,
            txs_count,
        )
    except Exception as e:
        logger.error("Ошибка при создании плана переносов: %s", e)
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def select_wallet_batch_for_move(cursor,
                                 source_table,
                                 target_table,
                                 batch_rows,
                                 plan_table='service_wallet_move_plan',
                                 wallet_scan_limit=None):
    if wallet_scan_limit is None:
        wallet_scan_limit = max(50000, int(batch_rows or 0))

    cursor.execute(
        """
        SELECT wallet_id, rows_count
        FROM {plan}
        WHERE source_table = ?
          AND target_table = ?
        LIMIT ?;
        """.format(plan=quote_identifier(plan_table)),
        (source_table, target_table, wallet_scan_limit),
    )
    selected_wallets = []
    selected_rows = 0
    for wallet_id, rows_count in cursor.fetchall():
        rows_count = int(rows_count or 0)
        if selected_wallets and selected_rows + rows_count > batch_rows:
            break
        selected_wallets.append(wallet_id)
        selected_rows += rows_count
        if selected_rows >= batch_rows:
            break
    return selected_wallets, selected_rows


def move_rows_by_wallet_plan(db_path,
                             plan_table='service_wallet_move_plan',
                             meta_table='service_wallet_move_meta',
                             batch_rows=SQL_MOVE_TXS_BATCH_ROWS):
    """
    Переносит строки по service_wallet_move_plan.
    Один батч = одна транзакция: INSERT в target, DELETE из source,
    DELETE обработанных кошельков из plan.
    """
    logger.info("start move_rows_by_wallet_plan")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        apply_large_scan_pragmas(cursor)
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_service_wallet_move_plan_batch
            ON {plan} (source_table, target_table, wallet_id, rows_count);
            """.format(plan=quote_identifier(plan_table))
        )
        conn.commit()

        total_rows = 0
        has_move_meta = table_exists(conn, meta_table)
        if has_move_meta:
            cursor.execute(
                "SELECT value FROM {} WHERE key = 'remaining_rows';".format(
                    quote_identifier(meta_table)
                )
            )
            meta_row = cursor.fetchone()
            if meta_row:
                total_rows = int(meta_row[0])
            else:
                cursor.execute(
                    "SELECT value FROM {} WHERE key = 'total_rows';".format(
                        quote_identifier(meta_table)
                    )
                )
                meta_row = cursor.fetchone()
                total_rows = int(meta_row[0]) if meta_row else 0
        else:
            logger.info(
                "Таблица %s отсутствует; полный SUM(rows_count) по plan пропущен, "
                "процентный progress будет недоступен до следующего полного построения плана.",
                meta_table,
            )
        processed_rows = 0
        batch_number = 0
        total_batches = (
            (total_rows + batch_rows - 1) // batch_rows
            if total_rows and batch_rows
            else None
        )
        progress_reporter = ProgressReporter(
            total_items=total_rows,
            step_name='wallet_plan_move',
            percent_step=2.0,
        )

        cursor.execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS temp_move_wallets (
                wallet_id TEXT PRIMARY KEY
            );
            """
        )
        conn.commit()

        # Сначала возвращаем кошельки, которые уже лежат в cold storage, но больше
        # не попадают под low-tx порог. После этого индекс few_tx_wallets.Wallet_id
        # больше не нужен и будет удален перед тяжелым INSERT в few_tx_wallets.
        preferred_directions = (
            ('few_tx_wallets', 'data_table'),
            ('data_table', 'few_tx_wallets'),
        )
        dropped_storage_index = False

        for preferred_source, preferred_target in preferred_directions:
            cursor.execute(
                """
                SELECT 1
                FROM {plan}
                WHERE source_table = ?
                  AND target_table = ?
                LIMIT 1;
                """.format(plan=quote_identifier(plan_table)),
                (preferred_source, preferred_target),
            )
            if not cursor.fetchone():
                continue

            if (
                preferred_source == 'data_table'
                and preferred_target == 'few_tx_wallets'
                and not dropped_storage_index
            ):
                drop_index_if_exists(db_path, 'idx_few_tx_wallets_wallet_id')
                dropped_storage_index = True

            source_table, target_table = preferred_source, preferred_target
            columns = get_table_column_names(conn, source_table)
            column_list = ", ".join(quote_identifier(col) for col in columns)
            source_column_list = ", ".join("src.{}".format(quote_identifier(col)) for col in columns)
            insert_sql = """
                INSERT INTO {target} ({columns})
                SELECT {source_columns}
                FROM {source} AS src
                JOIN temp_move_wallets AS batch
                  ON batch.wallet_id = src.Wallet_id;
            """.format(
                target=quote_identifier(target_table),
                columns=column_list,
                source_columns=source_column_list,
                source=quote_identifier(source_table),
            )
            delete_source_sql = """
                DELETE FROM {source}
                WHERE Wallet_id IN (SELECT wallet_id FROM temp_move_wallets);
            """.format(source=quote_identifier(source_table))
            delete_plan_sql = """
                DELETE FROM {plan}
                WHERE source_table = ?
                  AND target_table = ?
                  AND wallet_id IN (SELECT wallet_id FROM temp_move_wallets);
            """.format(plan=quote_identifier(plan_table))

            while True:
                wallet_ids, batch_row_count = select_wallet_batch_for_move(
                    cursor,
                    source_table,
                    target_table,
                    batch_rows,
                    plan_table=plan_table,
                )
                if not wallet_ids:
                    break

                batch_started_at = time.perf_counter()
                cursor.execute("BEGIN;")
                cursor.execute("DELETE FROM temp_move_wallets;")
                cursor.executemany(
                    "INSERT INTO temp_move_wallets (wallet_id) VALUES (?);",
                    [(wallet_id,) for wallet_id in wallet_ids],
                )
                cursor.execute(insert_sql)
                inserted_count = cursor.rowcount
                cursor.execute(delete_source_sql)
                deleted_count = cursor.rowcount
                cursor.execute(delete_plan_sql, (source_table, target_table))
                if has_move_meta:
                    cursor.execute(
                        """
                        UPDATE {meta}
                        SET value = MAX(value - ?, 0)
                        WHERE key = 'remaining_rows';
                        """.format(meta=quote_identifier(meta_table)),
                        (int(batch_row_count or 0),),
                    )
                conn.commit()

                batch_number += 1
                batch_duration_sec = time.perf_counter() - batch_started_at
                remaining_batches = (
                    max(total_batches - batch_number, 0)
                    if total_batches is not None
                    else None
                )
                eta_human = (
                    format_seconds_human(remaining_batches * batch_duration_sec)
                    if remaining_batches is not None
                    else "unknown"
                )
                processed_rows += batch_row_count
                logger.info(
                    "Батч %s -> %s: batch=%s/%s wallets=%s planned_rows=%s "
                    "inserted=%s deleted=%s batch_sec=%.2f eta_by_last_batch=%s",
                    source_table,
                    target_table,
                    batch_number,
                    total_batches if total_batches is not None else "unknown",
                    len(wallet_ids),
                    batch_row_count,
                    inserted_count,
                    deleted_count,
                    batch_duration_sec,
                    eta_human,
                )
                progress_reporter.emit(processed_rows)

        logger.info("Перенос по service_wallet_move_plan завершен.")
    except Exception as e:
        logger.error("Ошибка при переносе по плану кошельков: %s", e)
        conn.rollback()
        raise
    finally:
        try:
            cursor.execute("DROP TABLE IF EXISTS temp_move_wallets;")
            conn.commit()
        except Exception:
            pass
        cursor.close()
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
            'temp_wallets',
            'service_wallet_targets',
            'service_wallet_move_plan',
            'service_wallet_move_meta',
            'service_move_to_few_rowids',
            'service_move_to_data_rowids',
            'service_rebuild_data_table',
            'service_rebuild_few_tx_wallets',
            'service_backup_data_table',
            'service_backup_few_tx_wallets',
            'service_wallet_counts_data',
            'service_wallet_counts_storage',
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


def vacuum_db(db_path):
    """
    Физически перепаковывает SQLite-файл после большого возврата строк.
    Запускать только после завершения переносов и закрытия транзакций.
    """
    logger.info("start vacuum_db")
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        apply_large_scan_pragmas(cursor)
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        cursor.execute("VACUUM;")
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        conn.commit()
        logger.info("VACUUM завершен.")
    except Exception as e:
        logger.error("Ошибка при VACUUM: %s", e)
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def analyze_db(db_path):
    """
    Обновляет статистику планировщика SQLite после финального состояния таблиц.
    Делается после VACUUM, потому что VACUUM переписывает физический файл БД.
    """
    logger.info("start analyze_db")
    conn = None
    cursor = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        apply_large_scan_pragmas(cursor)
        cursor.execute("ANALYZE;")
        conn.commit()
        logger.info("ANALYZE завершен.")
    except Exception as e:
        logger.error("Ошибка при ANALYZE: %s", e)
        if conn:
            conn.rollback()
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
    "idx_block_height_wallet_id",
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
    logger.info(
        "start create_indexes: создаем обязательные индексы data_table "
        "(idx_wallet_id, idx_block_height, idx_txs_blocktime, idx_block_height_wallet_id)."
    )
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
        if 'Block_height' in cols and 'Wallet_id' in cols:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_block_height_wallet_id "
                "ON data_table (Block_height, Wallet_id);"
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
        "Старт move_txs plan-based: целевое состояние кошельков будет собрано по data_table "
        "и few_tx_wallets. Перенос выполняется батчами по кошелькам с возобновляемым "
        "планом service_wallet_move_plan."
    )

    warn_required_data_table_indexes(BLOCKS_SQL_DATA, "service.move_txs")
    create_target_table(BLOCKS_SQL_DATA, target_table="few_tx_wallets", source_table="data_table")  # #коммент: гарантируем наличие хранилищной таблицы
    check_db_structures(BLOCKS_SQL_DATA)                                                            # #коммент: проверяем совместимость схем без тяжелой дедупликации
    optimize_db(BLOCKS_SQL_DATA)                                                                    # #коммент: включаем WAL/synchronous=NORMAL и temp_store=FILE для больших scan
    cleanup_stale_rebuild_tables(BLOCKS_SQL_DATA)                                                   # #коммент: удаляем черновики старых rebuild/rowid-подходов, но не трогаем active plan
    create_wallet_id_indexes_for_move(BLOCKS_SQL_DATA)                                              # #коммент: Wallet_id нужен для GROUP BY/JOIN/DELETE в обеих рабочих таблицах
    drop_non_wallet_data_table_indexes(BLOCKS_SQL_DATA)                                             # #коммент: Block_height/Block_time индексы замедляют массовый DELETE и будут пересозданы в конце
    create_wallet_move_plan(BLOCKS_SQL_DATA, LOW_TX_WALLET_MAX_TX_COUNT)                            # #коммент: если plan уже существует, продолжаем с места остановки
    # ВАЖНО:
    # После создания service_wallet_move_plan сценарий становится возобновляемым:
    # каждый батч коммитит INSERT в целевую таблицу, DELETE из исходной таблицы
    # и удаление обработанных кошельков из plan одной транзакцией.
    # При остановке нужно просто снова запустить move_txs; пересчет GROUP BY будет пропущен.
    move_rows_by_wallet_plan(BLOCKS_SQL_DATA, batch_rows=SQL_MOVE_TXS_BATCH_ROWS)                      # #коммент: переносим только кошельки, лежащие не в своей целевой таблице
    create_indexes(BLOCKS_SQL_DATA)                                                                   # #коммент: финальная проверка рабочих индексов data_table
    check_required_data_table_indexes(BLOCKS_SQL_DATA)                                                 # #коммент: явно подтверждаем готовность рабочей таблицы
    cleanup_move_txs_service_tables(BLOCKS_SQL_DATA)                                                   # #коммент: удаляем service-таблицы только после успешной проверки
    set_txs_moved_state(True)                                                                          # #коммент: фиксируем, что строки разнесены между data_table и few_tx_wallets

    # TODO(iteration_12 / maintenance): рассмотреть aggressive maintenance режим
    # для ручных окон обслуживания: locking_mode=EXCLUSIVE, больший cache_size,
    # mmap_size и настройку checkpoint. Это может ускорить bulk-перенос, но делает
    # БД непригодной для параллельной работы на время операции.
    # TODO(iteration_12 / architecture): вместо физического переноса сотен миллионов
    # строк рассмотреть таблицу классификации кошельков и фильтрацию рабочих
    # pipeline-запросов по ней. Если цель - исключить low-tx кошельки из расчетов,
    # это может быть быстрее и надежнее физического разнесения строк.

    logger.info("Работа move_txs plan-based завершена. Финальный COUNT(*) по большим таблицам пропущен.")


def move_txs_back(run_vacuum=True, run_analyze=True):
    """
    Возвращает все строки из few_tx_wallets обратно в data_table.

    Сценарий нужен для выхода из legacy-модели физического разнесения строк.
    Возврат выполняется батчами и возобновляем: если процесс остановлен,
    следующий запуск продолжит с оставшихся строк в few_tx_wallets.
    """
    print_now()
    logger.info(
        "Старт move_txs_back: возвращаем все строки из few_tx_wallets в data_table. "
        "После успешного завершения TXS_MOVED будет False."
    )

    create_target_table(BLOCKS_SQL_DATA, target_table="few_tx_wallets", source_table="data_table")
    check_db_structures(BLOCKS_SQL_DATA)
    optimize_db(BLOCKS_SQL_DATA)

    # На возврате индексы data_table/few_tx_wallets не нужны для выбора батчей:
    # работаем по rowid. Их поддержка только замедляет массовые INSERT/DELETE.
    drop_data_table_runtime_indexes(BLOCKS_SQL_DATA)
    drop_index_if_exists(BLOCKS_SQL_DATA, "idx_few_tx_wallets_wallet_id")

    return_few_tx_wallets_to_data_table(
        BLOCKS_SQL_DATA,
        source_table="few_tx_wallets",
        target_table="data_table",
        batch_size=SQL_MOVE_TXS_BACK_BATCH_ROWS,
    )

    cleanup_move_txs_service_tables(BLOCKS_SQL_DATA)
    create_indexes(BLOCKS_SQL_DATA)
    check_required_data_table_indexes(BLOCKS_SQL_DATA)
    set_txs_moved_state(False)

    if run_vacuum:
        vacuum_db(BLOCKS_SQL_DATA)
    if run_analyze:
        analyze_db(BLOCKS_SQL_DATA)

    logger.info(
        "move_txs_back завершен: данные собраны в data_table, service-таблицы очищены, "
        "индексы проверены, TXS_MOVED=False."
    )


if __name__ == "__main__":
    moving_txs()
