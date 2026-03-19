import sqlite3
import traceback
from pathlib import Path
import pandas as pd

from modules.logger.logger import setup_logging

logger = setup_logging(__name__)


def get_all_table_names(db_path):
    """
    Получает список имён всех таблиц в базе данных, исключая служебные таблицы.
    """
    if isinstance(db_path, Path):
        db_path = str(db_path)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # #comment: исключаем таблицы, начинающиеся с 'sqlite_'
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return tables
    except Exception as e:
        logger.error(f"Ошибка при получении списка таблиц: {e}")
        return []


def fetch_last_five_rows(db_path, table_name=None):
    """
    Извлекает последние 5 строк из таблицы(ц), сортируя по Block_height в порядке убывания.
    Если table_name=None, функция применяется ко всем таблицам.
    """
    # #comment: Если table_name не указан, перебираем все таблицы
    if table_name is None:
        tables = get_all_table_names(db_path)
        all_results = {}
        for tbl in tables:
            all_results[tbl] = fetch_last_five_rows(db_path, tbl)
        return all_results

    try:
        if isinstance(db_path, Path):
            db_path = str(db_path)
        
        logger.info(f"Подключение к базе данных по пути: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверка существования таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        table_exists = cursor.fetchone()
        if not table_exists:
            logger.warning(f"Таблица '{table_name}' не найдена.")
            return []

        limit = 5
        if not isinstance(limit, int) or limit <= 0:
            logger.warning("Значение limit должно быть положительным целым числом.")
            return []

        # Выполнение запроса для извлечения последних 5 строк
        query = f"SELECT * FROM {table_name} ORDER BY Block_height DESC LIMIT {limit};"
        cursor.execute(query)
        rows = cursor.fetchall()

        # Получение имён столбцов
        cursor.execute(f"PRAGMA table_info('{table_name}');")
        columns_info = cursor.fetchall()
        column_names = [info[1] for info in columns_info]

        # Преобразование строк в словари для удобства чтения
        last_five_rows = [dict(zip(column_names, row)) for row in rows]

        cursor.close()
        conn.close()

        if last_five_rows:
            logger.info(f"Последние {limit} строк из таблицы '{table_name}':")
            for row in last_five_rows:
                logger.info(str(row))
        else:
            logger.info(f"В таблице '{table_name}' нет записей.")

        return last_five_rows

    except Exception as e:
        logger.error(f"Ошибка при извлечении строк: {e}")
        traceback.print_exc()
        return []


def count_block_height_above(db_path, threshold, table_name=None):
    """
    Подсчитывает количество строк в таблице(ц), где Block_height превышает заданный порог.
    Если table_name=None, функция применяется ко всем таблицам.
    """
    # #comment: Если table_name не указан, перебираем все таблицы
    if table_name is None:
        tables = get_all_table_names(db_path)
        counts = {}
        for tbl in tables:
            counts[tbl] = count_block_height_above(db_path, threshold, tbl)
        return counts

    try:
        if isinstance(db_path, Path):
            db_path = str(db_path)
        
        logger.info(f"Подключение к базе данных по пути: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверка существования таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        table_exists = cursor.fetchone()
        if not table_exists:
            logger.warning(f"Таблица '{table_name}' не найдена.")
            return 0

        # Выполнение запроса для подсчёта строк
        query = f"SELECT COUNT(*) FROM {table_name} WHERE Block_height > ?;"
        cursor.execute(query, (threshold,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result:
            count = result[0]
            formatted_count = f"{count:,}".replace(",", " ")
            logger.info(f"Количество строк, где Block_height > {threshold} в таблице '{table_name}': {formatted_count}")
            return count
        else:
            logger.warning("Не удалось получить результат запроса.")
            return 0

    except Exception as e:
        logger.error(f"Ошибка при подсчёте строк: {e}")
        traceback.print_exc()
        return 0


def count_total_rows(db_path, table_name=None):
    """
    Подсчитывает общее количество строк в таблице(ц).
    Если table_name=None, функция применяется ко всем таблицам.
    """
    # #comment: Если table_name не указан, перебираем все таблицы
    if table_name is None:
        tables = get_all_table_names(db_path)
        total_counts = {}
        for tbl in tables:
            total_counts[tbl] = count_total_rows(db_path, tbl)
        return total_counts

    try:
        if isinstance(db_path, Path):
            db_path = str(db_path)
        
        logger.info(f"Подключение к базе данных по пути: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверка существования таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        table_exists = cursor.fetchone()
        if not table_exists:
            logger.warning(f"Таблица '{table_name}' не найдена.")
            return 0

        # Выполнение запроса для подсчёта общего количества строк
        query = f"SELECT COUNT(*) FROM {table_name};"
        cursor.execute(query)
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result:
            count = result[0]
            formatted_count = f"{count:,}".replace(",", " ")
            logger.info(f"Общее количество строк в таблице '{table_name}': {formatted_count}")
            return count
        else:
            logger.warning("Не удалось получить результат запроса.")
            return 0

    except Exception as e:
        logger.error(f"Ошибка при подсчёте общего количества строк: {e}")
        traceback.print_exc()
        return 0


def print_db_schema(db_path, table_name=None):
    """
    Выводит схему таблицы(ц).
    Если table_name=None, функция применяется ко всем таблицам.
    """
    # #comment: Если table_name не указан, перебираем все таблицы
    if table_name is None:
        tables = get_all_table_names(db_path)
        for tbl in tables:
            print_db_schema(db_path, tbl)
        return

    try:
        if isinstance(db_path, Path):
            db_path = str(db_path)
        
        logger.info(f"Подключение к базе данных по пути: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(f"PRAGMA table_info('{table_name}');")
        columns_info = cursor.fetchall()

        if columns_info:
            logger.info(f"Схема таблицы '{table_name}':")
            for column in columns_info:
                cid, name, type_, notnull, dflt_value, pk = column
                logger.info(f" - Столбец: {name}, Тип данных: {type_}, NOT NULL: {notnull}, Значение по умолчанию: {dflt_value}, Первичный ключ: {pk}")
        else:
            logger.warning(f"Таблица '{table_name}' не найдена.")

        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"Ошибка при получении схемы таблицы: {e}")
        traceback.print_exc()


def get_sqlite_stat1(db_path):
    """
    Извлекает содержимое системной таблицы sqlite_stat1.
    """
    conn = None  # #comment: инициализация переменной для безопасного закрытия соединения
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sqlite_stat1;")
        stat_data = cursor.fetchall()
        cursor.close()
        return stat_data
    except sqlite3.Error as e:
        logger.error(f"Ошибка при работе с базой данных: {e}")
        return None
    finally:
        if conn:
            conn.close()


def recreate_indexes(db_path, table_name=None, wallet_index_name='idx_wallet_id', timestamp_index_name='idx_timestamp'):
    """
    Пересоздает индексы для столбцов Wallet_id и timestamp.
    Если table_name=None, функция применяется ко всем таблицам.
    """
    # #comment: Если table_name не указан, перебираем все таблицы
    if table_name is None:
        tables = get_all_table_names(db_path)
        for tbl in tables:
            recreate_indexes(db_path, tbl, wallet_index_name, timestamp_index_name)
        return

    try:
        if isinstance(db_path, Path):
            db_path = str(db_path)
        
        logger.info(f"Подключение к базе данных по пути: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info(f"Удаляем индекс {wallet_index_name} (если существует) для таблицы '{table_name}'...")
        cursor.execute(f"DROP INDEX IF EXISTS {wallet_index_name};")  # #comment: удаление индекса по Wallet_id
        
        logger.info(f"Создаем новый индекс {wallet_index_name} на столбец Wallet_id в таблице '{table_name}'...")
        cursor.execute(f"CREATE INDEX {wallet_index_name} ON {table_name}(Wallet_id);")  # #comment: создание индекса по Wallet_id

        logger.info(f"Удаляем индекс {timestamp_index_name} (если существует) для таблицы '{table_name}'...")
        cursor.execute(f"DROP INDEX IF EXISTS {timestamp_index_name};")  # #comment: удаление индекса по timestamp
        
        logger.info(f"Создаем новый индекс {timestamp_index_name} на столбец timestamp в таблице '{table_name}'...")
        cursor.execute(f"CREATE INDEX {timestamp_index_name} ON {table_name}(timestamp);")  # #comment: создание индекса по timestamp
        
        logger.info("Обновляем статистику базы данных командой ANALYZE...")
        cursor.execute("ANALYZE;")  # #comment: обновление статистики
        
        conn.commit()  # #comment: фиксируем изменения
        logger.info(f"Пересоздание индексов завершено успешно для таблицы '{table_name}'.")
        
    except Exception as e:
        logger.error(f"Ошибка при пересоздании индексов: {e}")
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    BLOCKS_SQL_DATA = r"C:\blocks_sql_data\blocks_sql_data_db.db"
    
    logger.info(f"Запуск работы с базой данных: {BLOCKS_SQL_DATA}")
    
    # stat_data = get_sqlite_stat1(BLOCKS_SQL_DATA)
    # print("Содержимое sqlite_stat1:", stat_data)
    
    # print("\nВывод схемы для всех таблиц:")
    # print_db_schema(BLOCKS_SQL_DATA)  # table_name=None -> обрабатываются все таблицы
    
    # total_rows = count_total_rows(BLOCKS_SQL_DATA)  # общее количество строк для всех таблиц
    # print("\nОбщее количество строк по таблицам:")
    # print(total_rows)
    
    # last_five_rows = fetch_last_five_rows(BLOCKS_SQL_DATA)  # последние 5 строк для каждой таблицы
    # print("\nПять последних строк для каждой таблицы:")
    # print(last_five_rows)
    
    recreate_indexes(BLOCKS_SQL_DATA)  # пересоздание индексов для всех таблиц
    
    logger.info("Работа завершена.")
