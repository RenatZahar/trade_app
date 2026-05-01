import sqlite3
import warnings
from pathlib import Path

from modules.sql_funcs.data_table_indexes import REQUIRED_DATA_TABLE_INDEXES
from settings.db_contracts import REQUIRED_DB_TABLES
from settings.paths import BLOCKS_SQL_DATA


def _warn(message):
    warnings.warn(message, RuntimeWarning, stacklevel=2)


def _connect_readonly(db_path):
    return sqlite3.connect(
        f"{db_path.as_uri()}?mode=ro",
        uri=True,
        timeout=1,
    )


def test_live_db_tables_emit_warning_when_not_in_schema_contract():
    """
    Warning-only check for drift between the live DB and the schema contract.

    Extra live tables are not always an error: they can be legacy, service, or
    experimental tables. The warning makes the drift visible without making CI
    depend on a local production DB.
    """
    db_path = Path(BLOCKS_SQL_DATA).expanduser().resolve(strict=False)
    if not db_path.exists():
        _warn(f"Боевая SQLite-БД не найдена: {db_path}")
        return

    try:
        conn = _connect_readonly(db_path)
        try:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%';
                """
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as error:
        _warn(f"Не удалось проверить таблицы боевой SQLite-БД {db_path}: {error}")
        return

    live_tables = {row[0] for row in rows}
    missing_required_tables = sorted(REQUIRED_DB_TABLES - live_tables)
    tables_without_contract = sorted(live_tables - REQUIRED_DB_TABLES)

    if missing_required_tables:
        _warn(
            "В боевой SQLite-БД отсутствуют обязательные таблицы из DB contract: "
            + ", ".join(missing_required_tables)
        )

    if tables_without_contract:
        _warn(
            "В боевой SQLite-БД есть таблицы без DB contract: "
            + ", ".join(tables_without_contract)
        )


def test_live_data_table_required_indexes_emit_warning_only():
    """
    Warning-only smoke check for the production SQLite DB.

    The test intentionally does not fail: missing indexes should be visible in
    the smoke output, while long-running maintenance work remains user-controlled.
    """
    db_path = Path(BLOCKS_SQL_DATA).expanduser().resolve(strict=False)
    if not db_path.exists():
        _warn(f"Боевая SQLite-БД не найдена: {db_path}")
        return

    try:
        conn = _connect_readonly(db_path)
        try:
            data_table_exists = conn.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'data_table';
                """
            ).fetchone()
            if data_table_exists is None:
                _warn(f"В боевой SQLite-БД нет таблицы data_table: {db_path}")
                return

            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                  AND tbl_name = 'data_table';
                """
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as error:
        _warn(f"Не удалось проверить индексы боевой SQLite-БД {db_path}: {error}")
        return

    index_names = {row[0] for row in rows}
    missing_indexes = sorted(REQUIRED_DATA_TABLE_INDEXES - index_names)
    if missing_indexes:
        _warn(
            "В боевой data_table отсутствуют обязательные индексы: "
            + ", ".join(missing_indexes)
        )
