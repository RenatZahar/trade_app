import logging
import sqlite3

from settings.db_contracts import REQUIRED_DATA_TABLE_INDEXES


logger = logging.getLogger("app")


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
            (table,),
        )
        if not cursor.fetchone():
            logger.info("Таблица data_table не найдена. Пропускаем создание индексов.")
            return

        cursor.execute(f"PRAGMA table_info({table});")
        cols = [col[1] for col in cursor.fetchall()]

        if "Wallet_id" in cols:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_wallet_id ON data_table (Wallet_id);"
            )
        if "Block_height" in cols:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_block_height ON data_table (Block_height);"
            )
        if "Block_time" in cols:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_txs_blocktime ON data_table(Block_time);"
            )
        if "Block_height" in cols and "Wallet_id" in cols:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_block_height_wallet_id "
                "ON data_table (Block_height, Wallet_id);"
            )
        conn.commit()
    except Exception as e:
        logger.error("Ошибка при создании индексов: %s", e)
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
