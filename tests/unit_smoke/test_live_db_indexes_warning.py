import sqlite3
import warnings
from pathlib import Path

from modules.sql_funcs.moving_txs import REQUIRED_DATA_TABLE_INDEXES
from settings.paths import BLOCKS_SQL_DATA


def _warn(message):
    warnings.warn(message, RuntimeWarning, stacklevel=2)


def _connect_readonly(db_path):
    return sqlite3.connect(
        f"{db_path.as_uri()}?mode=ro",
        uri=True,
        timeout=1,
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
