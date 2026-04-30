# удаление строк с кошельками у которых одна или две txs с последующим обслуживанием
# TODO(iteration_12): вероятно избыточно. Файл дублирует старый maintenance-подход
# удаления/анализа строк; физический перенос кошельков архивирован в docs/experiments.
# Не запускать без отдельного design review на актуальной большой БД.

import sqlite3
from pathlib import Path
import logging
import sys
import time
import traceback

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def set_pragma_settings(conn):
    """
    Устанавливает настройки PRAGMA для оптимизации производительности.
    
    :param conn: Объект соединения SQLite.
    """
    cursor = conn.cursor()
    logger.info("Устанавливаем PRAGMA настройки для оптимизации производительности.")
    cursor.execute("PRAGMA synchronous = OFF;")
    cursor.execute("PRAGMA journal_mode = MEMORY;")
    cursor.execute("PRAGMA temp_store = MEMORY;")
    cursor.execute("PRAGMA cache_size = -100000;")  # ~100MB
    conn.commit()

def ensure_indexes(conn, table_name):
    """
    Убеждаемся, что необходимые индексы существуют. Если нет — создаём их.
    
    :param conn: Объект соединения SQLite.
    :param table_name: Имя таблицы, для которой проверяются индексы.
    """
    cursor = conn.cursor()
    
    # Список необходимых индексов: (имя индекса, столбец)
    required_indexes = [
        ('idx_wallet_id', 'Wallet_id'),
        ('idx_block_height', 'Block_height'),
    ]
    
    for index_name, column_name in required_indexes:
        cursor.execute("""
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type='index' AND name=? AND tbl_name=?;
        """, (index_name, table_name))
        exists = cursor.fetchone()[0]
        if not exists:
            logger.info(f"Индекс {index_name} на столбец {column_name} отсутствует. Создаём индекс.")
            cursor.execute(f"CREATE INDEX {index_name} ON {table_name} ({column_name});")
        else:
            logger.info(f"Индекс {index_name} уже существует.")
    
    conn.commit()

def delete_wallets_with_transactions(conn, table_name, transaction_count, batch_size=100000):
    """
    Удаляет все строки из таблицы, где Wallet_id имеет ровно transaction_count транзакций.
    Удаление выполняется партиями для оптимизации производительности.
    
    :param conn: Объект соединения SQLite.
    :param table_name: Имя таблицы.
    :param transaction_count: Количество транзакций для удаления.
    :param batch_size: Размер партии (количество Wallet_id за раз).
    """
    cursor = conn.cursor()
    
    logger.info(f"Начинаем удаление Wallet_id с {transaction_count} транзакциями.")
    
    # Создание временной таблицы с Wallet_id для удаления
    logger.info("Создаём временную таблицу для Wallet_id, подлежащих удалению.")
    cursor.execute("DROP TABLE IF EXISTS temp_wallets_to_delete;")
    cursor.execute(f"""
        CREATE TEMP TABLE temp_wallets_to_delete AS
        SELECT Wallet_id
        FROM {table_name}
        GROUP BY Wallet_id
        HAVING COUNT(Transaction_id) = ?
    """, (transaction_count,))
    conn.commit()
    
    # Создание индекса на временной таблице для ускорения удаления
    logger.info("Создаём индекс на временной таблице.")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_temp_wallet_id ON temp_wallets_to_delete (Wallet_id);")
    conn.commit()
    
    # Получаем общее количество Wallet_id для удаления
    cursor.execute("SELECT COUNT(*) FROM temp_wallets_to_delete;")
    wallets_to_delete = cursor.fetchone()[0]
    logger.info(f"Найдено {wallets_to_delete} Wallet_id с {transaction_count} транзакциями для удаления.")
    
    if wallets_to_delete == 0:
        logger.info(f"Нет Wallet_id с {transaction_count} транзакциями для удаления.")
        return
    
    # Определяем количество партий
    total_batches = (wallets_to_delete // batch_size) + (1 if wallets_to_delete % batch_size != 0 else 0)
    logger.info(f"Удаление будет выполнено в {total_batches} партиях по {batch_size} Wallet_id каждая.")
    
    for batch_num in range(total_batches):
        logger.info(f"Начинается удаление партии {batch_num + 1} из {total_batches}.")
        # Начало транзакции
        cursor.execute("BEGIN TRANSACTION;")
        
        # Удаление партии Wallet_id
        delete_query = f"""
            DELETE FROM {table_name}
            WHERE Wallet_id IN (
                SELECT Wallet_id FROM temp_wallets_to_delete
                LIMIT ? OFFSET ?
            );
        """
        cursor.execute(delete_query, (batch_size, batch_num * batch_size))
        conn.commit()
        
        logger.info(f"Партия {batch_num + 1} из {total_batches} удалена.")
    
    logger.info(f"Удаление Wallet_id с {transaction_count} транзакциями завершено.")

def perform_db_maintenance(conn):
    """
    Выполняет обслуживание базы данных: VACUUM и ANALYZE.
    
    :param conn: Объект соединения SQLite.
    """
    cursor = conn.cursor()
    try:
        logger.info("Выполняется VACUUM...")
        start_time = time.time()
        cursor.execute("VACUUM;")
        elapsed_time = time.time() - start_time
        logger.info(f"VACUUM завершён за {elapsed_time:.2f} секунд.")
        
        logger.info("Выполняется ANALYZE...")
        start_time = time.time()
        cursor.execute("ANALYZE;")
        elapsed_time = time.time() - start_time
        logger.info(f"ANALYZE завершён за {elapsed_time:.2f} секунд.")
        
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при выполнении обслуживания базы данных: {e}")

def analyze_wallet_transactions(db_path, table_name):
    """
    Анализирует количество строк в таблице и подсчитывает:
    1. Общее количество строк.
    
    :param db_path: Путь к базе данных SQLite.
    :param table_name: Имя таблицы.
    :return: Общее количество строк в виде числа.
    """
    if isinstance(db_path, Path):
        db_path = str(db_path)
    
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Проверка на существование таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        if cursor.fetchone() is None:
            raise ValueError(f"Таблица '{table_name}' не найдена в базе данных.")

        # Общее количество строк в таблице
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        total_rows = cursor.fetchone()[0]
        # print(f"Общее количество строк в таблице: {total_rows}")

        return total_rows

    finally:
        conn.close()
def count_wallet_transactions_and_rows(db_path):
    """
    Подключается к базе данных и подсчитывает количество кошельков и общее количество строк (транзакций)
    для кошельков с 1, 2 и 3 транзакциями.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Внутренний запрос группирует строки по Wallet_id, подсчитывая число транзакций (строк) для каждого кошелька.
        # Внешний запрос затем группирует результаты по этому числу (cnt) и считает:
        # - Количество кошельков (wallet_count) с таким числом транзакций.
        # - Общее число строк (row_count), что фактически равно cnt * wallet_count.
        query = """
        SELECT
            cnt,
            COUNT(*) AS wallet_count,
            SUM(cnt) AS row_count
        FROM (
            SELECT Wallet_id, COUNT(*) AS cnt
            FROM few_tx_wallets
            GROUP BY Wallet_id
        ) sub
        WHERE cnt IN (1, 2, 3)
        GROUP BY cnt;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        logger.info("Результаты группировки:")
        for cnt, wallet_count, row_count in results:
            logger.info(f"Кошельки с {cnt} транзакциями: {wallet_count} кошельков, всего {row_count} строк")
            
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()
        
if __name__ == "__main__":
    BLOCKS_SQL_DATA = r"C:\blocks_sql_data\blocks_sql_data_db.db"

    # Выполняем обслуживание базы данных
    logger.info("Начинается обслуживание базы данных (VACUUM и ANALYZE).")
    conn = sqlite3.connect(BLOCKS_SQL_DATA)
    try:
        perform_db_maintenance(conn)
    finally:
        conn.close()
    logger.info("Обслуживание базы данных завершено.")
    
    table_name = 'data_table'
    # Анализируем таблицу после удаления
    logger.info("Проводится анализ таблицы")
    result_after = analyze_wallet_transactions(BLOCKS_SQL_DATA, table_name)
    # print("Результаты анализа после удаления:")
    logger.info(f"Общее количество строк в таблице: {result_after}")

    # подсчет кол-ва кошельков с 1, 2 и 3 txs
    count_wallet_transactions_and_rows(BLOCKS_SQL_DATA)
