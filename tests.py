import sqlite3
import traceback
from pathlib import Path
import pandas as pd


def fetch_last_five_rows(db_path, table_name='data_table'):
    """
    Извлекает последние 5 строк из таблицы, сортируя по Block_height в порядке убывания.

    :param db_path: Путь к базе данных SQLite.
    :param table_name: Имя таблицы (по умолчанию 'data_table').
    :return: Список словарей, представляющих последние 5 строк.
    """
    try:
        # Убедимся, что путь к базе данных является строкой
        if isinstance(db_path, Path):
            db_path = str(db_path)
        
        print(f"Подключение к базе данных по пути: {db_path}")
        # Установка соединения с базой данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверка существования таблицы
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name=?;
        """, (table_name,))
        table_exists = cursor.fetchone()
        if not table_exists:
            print(f"Таблица '{table_name}' не найдена.")
            return []

        # Убедимся, что значение limit является целым числом
        limit = 5
        if not isinstance(limit, int) or limit <= 0:
            print("Значение limit должно быть положительным целым числом.")
            return []

        # Выполнение запроса для извлечения последних 5 строк
        # Сортировка по Block_height в порядке убывания предполагает, что последние записи имеют наибольшие значения Block_height
        query = f"""
            SELECT * FROM {table_name}
            ORDER BY Block_height DESC
            LIMIT {limit};
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        # Получение имен столбцов
        cursor.execute(f"PRAGMA table_info('{table_name}');")
        columns_info = cursor.fetchall()
        column_names = [info[1] for info in columns_info]

        # Преобразование строк в словари для удобства чтения
        last_five_rows = [dict(zip(column_names, row)) for row in rows]

        # Закрытие соединения
        cursor.close()
        conn.close()

        if last_five_rows:
            print(f"Последние {limit} строк из таблицы '{table_name}':")
            for row in last_five_rows:
                print(row)
        else:
            print(f"В таблице '{table_name}' нет записей.")

        return last_five_rows

    except Exception as e:
        print(f"Ошибка при извлечении строк: {e}")
        traceback.print_exc()
        return []
    

def count_block_height_above(db_path, threshold, table_name='data_table'):
    """
    Подсчитывает количество строк в таблице, где Block_height превышает заданный порог.

    :param db_path: Путь к базе данных SQLite.
    :param threshold: Пороговое значение для Block_height.
    :param table_name: Имя таблицы (по умолчанию 'data_table').
    :return: Количество строк, соответствующих условию.
    """
    try:
        if isinstance(db_path, Path):
            db_path = str(db_path)
        
        print(f"Подключение к базе данных по пути: {db_path}")
        # Установка соединения с базой данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверка существования таблицы
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name=?;
        """, (table_name,))
        table_exists = cursor.fetchone()
        if not table_exists:
            print(f"Таблица '{table_name}' не найдена.")
            return 0

        # Выполнение запроса для подсчёта строк
        query = f"SELECT COUNT(*) FROM {table_name} WHERE Block_height > ?;"
        cursor.execute(query, (threshold,))
        result = cursor.fetchone()

        # Закрытие соединения
        cursor.close()
        conn.close()

        if result:
            count = result[0]
            # Форматирование числа с пробелами как разделителями тысяч
            formatted_count = f"{count:,}".replace(",", " ")
            print(f"Количество строк, где Block_height > {threshold}: {formatted_count}")
            return count
        else:
            print("Не удалось получить результат запроса.")
            return 0

    except Exception as e:
        print(f"Ошибка при подсчёте строк: {e}")
        traceback.print_exc()
        return 0



def count_total_rows(db_path, table_name='data_table'):
    """
    Подсчитывает общее количество строк в таблице.

    :param db_path: Путь к базе данных SQLite.
    :param table_name: Имя таблицы (по умолчанию 'data_table').
    :return: Общее количество строк.
    """
    try:
        if isinstance(db_path, Path):
            db_path = str(db_path)
        
        print(f"Подключение к базе данных по пути: {db_path}")
        # Установка соединения с базой данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверка существования таблицы
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name=?;
        """, (table_name,))
        table_exists = cursor.fetchone()
        if not table_exists:
            print(f"Таблица '{table_name}' не найдена.")
            return 0

        # Выполнение запроса для подсчёта общего количества строк
        query = f"SELECT COUNT(*) FROM {table_name};"
        cursor.execute(query)
        result = cursor.fetchone()

        # Закрытие соединения
        cursor.close()
        conn.close()

        if result:
            count = result[0]
            # Форматирование числа с пробелами как разделителями тысяч
            formatted_count = f"{count:,}".replace(",", " ")
            print(f"Общее количество строк в таблице '{table_name}': {formatted_count}")
            return count
        else:
            print("Не удалось получить результат запроса.")
            return 0

    except Exception as e:
        print(f"Ошибка при подсчёте общего количества строк: {e}")
        traceback.print_exc()
        return 0

def print_db_schema(db_path, table_name='data_table'):
    """
    Выводит схему таблицы.

    :param db_path: Путь к базе данных SQLite.
    :param table_name: Имя таблицы (по умолчанию 'data_table').
    """
    try:
        if isinstance(db_path, Path):
            db_path = str(db_path)
        
        print(f"Подключение к базе данных по пути: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(f"PRAGMA table_info('{table_name}');")
        columns_info = cursor.fetchall()

        if columns_info:
            print(f"Схема таблицы '{table_name}':")
            for column in columns_info:
                cid, name, type_, notnull, dflt_value, pk = column
                print(f" - Столбец: {name}, Тип данных: {type_}, NOT NULL: {notnull}, Значение по умолчанию: {dflt_value}, Первичный ключ: {pk}")
        else:
            print(f"Таблица '{table_name}' не найдена.")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Ошибка при получении схемы таблицы: {e}")
        traceback.print_exc()

